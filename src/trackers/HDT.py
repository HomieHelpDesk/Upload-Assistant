import requests
import asyncio
import re
import os
import cli_ui
import httpx
from str2bool import str2bool
from bs4 import BeautifulSoup
from unidecode import unidecode
from pymediainfo import MediaInfo
from src.trackers.COMMON import COMMON
from src.exceptions import *  # noqa F403
from src.console import console


class HDT():

    def __init__(self, config):
        self.config = config
        self.tracker = 'HDT'
        self.source_flag = 'hd-torrents.org'
        self.username = config['TRACKERS'][self.tracker].get('username', '').strip()
        self.password = config['TRACKERS'][self.tracker].get('password', '').strip()
        self.signature = "\n[center][url=https://github.com/HomieHelpDesk/HHD-Upload]Genuine HHD Torrent[/url][/center]"
        self.banned_groups = [""]

    async def get_category_id(self, meta):
        if meta['category'] == 'MOVIE':
            # BDMV
            if meta.get('is_disc', '') == "BDMV" or meta.get('type', '') == "DISC":
                if meta['resolution'] == '2160p':
                    # 70 = Movie/UHD/Blu-Ray
                    cat_id = 70
                if meta['resolution'] in ('1080p', '1080i'):
                    # 1 = Movie/Blu-Ray
                    cat_id = 1

            # REMUX
            if meta.get('type', '') == 'REMUX':
                if meta.get('uhd', '') == 'UHD' and meta['resolution'] == '2160p':
                    # 71 = Movie/UHD/Remux
                    cat_id = 71
                else:
                    # 2 = Movie/Remux
                    cat_id = 2

            # REST OF THE STUFF
            if meta.get('type', '') not in ("DISC", "REMUX"):
                if meta['resolution'] == '2160p':
                    # 64 = Movie/2160p
                    cat_id = 64
                elif meta['resolution'] in ('1080p', '1080i'):
                    # 5 = Movie/1080p/i
                    cat_id = 5
                elif meta['resolution'] == '720p':
                    # 3 = Movie/720p
                    cat_id = 3

        if meta['category'] == 'TV':
            # BDMV
            if meta.get('is_disc', '') == "BDMV" or meta.get('type', '') == "DISC":
                if meta['resolution'] == '2160p':
                    # 72 = TV Show/UHD/Blu-ray
                    cat_id = 72
                if meta['resolution'] in ('1080p', '1080i'):
                    # 59 = TV Show/Blu-ray
                    cat_id = 59

            # REMUX
            if meta.get('type', '') == 'REMUX':
                if meta.get('uhd', '') == 'UHD' and meta['resolution'] == '2160p':
                    # 73 = TV Show/UHD/Remux
                    cat_id = 73
                else:
                    # 60 = TV Show/Remux
                    cat_id = 60

            # REST OF THE STUFF
            if meta.get('type', '') not in ("DISC", "REMUX"):
                if meta['resolution'] == '2160p':
                    # 65 = TV Show/2160p
                    cat_id = 65
                elif meta['resolution'] in ('1080p', '1080i'):
                    # 30 = TV Show/1080p/i
                    cat_id = 30
                elif meta['resolution'] == '720p':
                    # 38 = TV Show/720p
                    cat_id = 38

        return cat_id

    async def edit_name(self, meta):
        hdt_name = meta['name']
        if meta['category'] == "TV" and meta.get('tv_pack', 0) == 0 and meta.get('episode_title_storage', '').strip() != '':
            hdt_name = hdt_name.replace(meta['episode'], f"{meta['episode']} {meta['episode_title_storage']}")
        if meta.get('type') in ('WEBDL', 'WEBRIP', 'ENCODE'):
            hdt_name = hdt_name.replace(meta['audio'], meta['audio'].replace(' ', '', 1))
        if 'DV' in meta.get('hdr', ''):
            hdt_name = hdt_name.replace(' DV ', ' DoVi ')

        hdt_name = ' '.join(hdt_name.split())
        hdt_name = re.sub(r"[^0-9a-zA-ZÀ-ÿ. &+'\-\[\]]+", "", hdt_name)
        hdt_name = hdt_name.replace(':', '').replace('..', ' ').replace('  ', ' ')
        return hdt_name

    async def upload(self, meta, disctype):
        common = COMMON(config=self.config)
        await common.edit_torrent(meta, self.tracker, self.source_flag)
        await self.edit_desc(meta)
        hdt_name = await self.edit_name(meta)
        cat_id = await self.get_category_id(meta)

        # Confirm the correct naming order for HDT
        cli_ui.info(f"HDT name: {hdt_name}")
        if meta.get('unattended', False) is False:
            hdt_confirm = cli_ui.ask_yes_no("Correct?", default=False)
            if hdt_confirm is not True:
                hdt_name_manually = cli_ui.ask_string("Please enter a proper name", default="")
                if hdt_name_manually == "":
                    console.print('No proper name given')
                    console.print("Aborting...")
                    return
                else:
                    hdt_name = hdt_name_manually

        # Upload
        hdt_desc = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'r', newline='', encoding='utf-8').read()
        torrent_path = f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]{meta['clean_name']}.torrent"

        with open(torrent_path, 'rb') as torrentFile:
            torrentFileName = unidecode(hdt_name)
            files = {
                'torrent': (f"{torrentFileName}.torrent", torrentFile, "application/x-bittorent")
            }
            data = {
                'filename': hdt_name,
                'category': cat_id,
                'info': hdt_desc.strip()
            }

            # 3D
            if "3D" in meta.get('3d', ''):
                data['3d'] = 'true'

            # HDR
            if "HDR" in meta.get('hdr', ''):
                if "HDR10+" in meta['hdr']:
                    data['HDR10'] = 'true'
                    data['HDR10Plus'] = 'true'
                else:
                    data['HDR10'] = 'true'
            if "DV" in meta.get('hdr', ''):
                data['DolbyVision'] = 'true'

            # IMDB
            if int(meta.get('imdb_id', '').replace('tt', '')) != 0:
                data['infosite'] = f"https://www.imdb.com/title/tt{meta['imdb_id']}/"

            # Full Season Pack
            if int(meta.get('tv_pack', '0')) != 0:
                data['season'] = 'true'
            else:
                data['season'] = 'false'

            # Anonymous check
            if meta['anon'] == 0 and bool(str2bool(str(self.config['TRACKERS'][self.tracker].get('anon', "False")))) is False:
                data['anonymous'] = 'false'
            else:
                data['anonymous'] = 'true'

            # Send
            url = "https://hd-torrents.net/upload.php"
            if meta['debug']:
                console.print(url)
                console.print("Data to be sent:", style="bold blue")
                console.print(data)
                console.print("Files being sent:", style="bold blue")
                console.print(files)
            with requests.Session() as session:
                cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/HDT.txt")

                if meta['debug']:
                    console.print(f"Cookie file path: {cookiefile}")

                session.cookies.update(await common.parseCookieFile(cookiefile))

                if meta['debug']:
                    console.print(f"Session cookies: {session.cookies}")

                up = session.post(url=url, data=data, files=files)
                torrentFile.close()

                # Debug response
                if meta['debug']:
                    console.print(f"Response URL: {up.url}")
                    console.print(f"Response Status Code: {up.status_code}")
                    console.print("Response Headers:", style="bold blue")
                    console.print(up.headers)
                    console.print("Response Text (truncated):", style="dim")
                    console.print(up.text[:500] + "...")

                # Match url to verify successful upload
                search = re.search(r"download\.php\?id\=([a-z0-9]+)", up.text)
                if search:
                    torrent_id = search.group(1)
                    if meta['debug']:
                        console.print(f"Upload Successful: Torrent ID {torrent_id}", style="bold green")

                    # Modding existing torrent for adding to client instead of downloading torrent from site
                    await common.add_tracker_torrent(meta, self.tracker, self.source_flag, self.config['TRACKERS']['HDT'].get('my_announce_url'), "")
                else:
                    console.print(data)
                    console.print("Failed to find download link in response text.", style="bold red")
                    console.print("Response Data (full):", style="dim")
                    console.print(up.text)
                    raise UploadException(f"Upload to HDT Failed: result URL {up.url} ({up.status_code}) was not expected", 'red')  # noqa F405
        return

    async def search_existing(self, meta, disctype):
        dupes = []
        console.print("[yellow]Searching for existing torrents on HDT...")

        common = COMMON(config=self.config)
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/HDT.txt")
        cookies = await common.parseCookieFile(cookiefile)

        search_url = "https://hd-torrents.net/torrents.php"

        async with httpx.AsyncClient(cookies=cookies, timeout=10.0) as client:
            csrfToken = await self.get_csrfToken(client, search_url)
            if int(meta['imdb_id'].replace('tt', '')) != 0:
                params = {
                    'csrfToken': csrfToken,
                    'search': meta['imdb_id'],
                    'active': '0',
                    'options': '2',
                    'category[]': await self.get_category_id(meta)
                }
            else:
                params = {
                    'csrfToken': csrfToken,
                    'search': meta['title'],
                    'category[]': await self.get_category_id(meta),
                    'options': '3'
                }

            try:
                response = await client.get(search_url, params=params)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    find = soup.find_all('a', href=True)
                    for each in find:
                        if each['href'].startswith('details.php?id='):
                            dupes.append(each.text)
                else:
                    console.print(f"[bold red]HTTP request failed. Status: {response.status_code}")

                await asyncio.sleep(0.5)

            except httpx.TimeoutException:
                console.print("[bold red]Request timed out while searching for existing torrents.")
            except httpx.RequestError as e:
                console.print(f"[bold red]An error occurred while making the request: {e}")
            except Exception as e:
                console.print(f"[bold red]Unexpected error: {e}")
                await asyncio.sleep(0.5)

        return dupes

    async def validate_credentials(self, meta):
        cookiefile = os.path.abspath(f"{meta['base_dir']}/data/cookies/HDT.txt")
        vcookie = await self.validate_cookies(meta, cookiefile)
        if vcookie is not True:
            console.print('[red]Failed to validate cookies. Please confirm that the site is up or export a fresh cookie file from the site')
            return False
        return True

    async def validate_cookies(self, meta, cookiefile):
        common = COMMON(config=self.config)
        url = "https://hd-torrents.net/index.php"
        cookiefile = f"{meta['base_dir']}/data/cookies/HDT.txt"
        if os.path.exists(cookiefile):
            with requests.Session() as session:
                session.cookies.update(await common.parseCookieFile(cookiefile))
                res = session.get(url=url)
                if meta['debug']:
                    console.print('[cyan]Cookies:')
                    console.print(session.cookies.get_dict())
                    console.print(res.url)
                if res.text.find("Logout") != -1:
                    return True
                else:
                    return False
        else:
            return False

    async def get_csrfToken(self, session, url):
        r = session.get(url)
        await asyncio.sleep(0.5)
        soup = BeautifulSoup(r.text, 'html.parser')
        csrfToken = soup.find('input', {'name': 'csrfToken'}).get('value')
        return csrfToken

    async def edit_desc(self, meta):
        # base = open(f"{meta['base_dir']}/tmp/{meta['uuid']}/DESCRIPTION.txt", 'r').read()
        with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/[{self.tracker}]DESCRIPTION.txt", 'w', newline='', encoding='utf-8') as descfile:
            if meta['is_disc'] != 'BDMV':
                # Beautify MediaInfo for HDT using custom template
                video = meta['filelist'][0]
                mi_template = os.path.abspath(f"{meta['base_dir']}/data/templates/MEDIAINFO.txt")
                if os.path.exists(mi_template):
                    media_info = MediaInfo.parse(video, output="STRING", full=False, mediainfo_options={"inform": f"file://{mi_template}"})
                    descfile.write(f"""[left][font=consolas]\n{media_info}\n[/font][/left]\n""")
                else:
                    console.print("[bold red]Couldn't find the MediaInfo template")
                    console.print("[green]Using normal MediaInfo for the description.")

                    with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/MEDIAINFO_CLEANPATH.txt", 'r', encoding='utf-8') as MI:
                        descfile.write(f"""[left][font=consolas]\n{MI.read()}\n[/font][/left]\n\n""")
            else:
                with open(f"{meta['base_dir']}/tmp/{meta['uuid']}/BD_SUMMARY_00.txt", 'r', encoding='utf-8') as BD_SUMMARY:
                    descfile.write(f"""[left][font=consolas]\n{BD_SUMMARY.read()}\n[/font][/left]\n\n""")

            # Add Screenshots
            images = meta['image_list']
            if len(images) > 0:
                for each in range(min(2, len(images))):
                    img_url = images[each]['img_url']
                    raw_url = images[each]['raw_url']
                    descfile.write(f'<a href="{raw_url}"><img src="{img_url}" height=137></a> ')

            descfile.close()
