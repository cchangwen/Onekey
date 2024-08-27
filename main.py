import os
import vdf
import winreg
import aiofiles
import traceback
import subprocess
import colorlog
import logging
import ujson as json
import time
import sys
import psutil
import asyncio
from aiohttp import ClientSession, ClientError
from pathlib import Path

# 初始化日志记录器
def init_log():
    logger = logging.getLogger('Onekey')
    logger.setLevel(logging.DEBUG)
    stream_handler = logging.StreamHandler()
    stream_handler.setLevel(logging.DEBUG)
    fmt_string = '%(log_color)s[%(name)s][%(levelname)s]%(message)s'
    log_colors = {
        'DEBUG': 'cyan',
        'INFO': 'green',
        'WARNING': 'yellow',
        'ERROR': 'red',
        'CRITICAL': 'purple'
    }
    fmt = colorlog.ColoredFormatter(fmt_string, log_colors=log_colors)
    stream_handler.setFormatter(fmt)
    logger.addHandler(stream_handler)
    return logger


# 生成配置文件
def gen_config_file():
    default_config ={
                    "Github_Personal_Token": "",
                    "Custom_Steam_Path": "",
                    "QA1": "温馨提示：Github_Personal_Token可在Github设置的最底下开发者选项找到，详情看教程",
                    "教程": "https://lyvx-my.sharepoint.com/:w:/g/personal/ikun_ikunshare_com/EWqIqyCElLNLo_CKfLbqix0BWU_O03HLzEHQKHdJYrUz-Q?e=79MZjw"
                    }
    with open("./config.json", "w", encoding="utf-8") as f:
        f.write(json.dumps(default_config, indent=2, ensure_ascii=False,
                escape_forward_slashes=False))
        f.close()
    log.info(' 🖱️ 程序可能为第一次启动，请填写配置文件后重新启动程序')


# 加载配置文件
def load_config():
    if not os.path.exists('./config.json'):
        gen_config_file()
        os.system('pause')
        sys.exit()
    else:
        with open("./config.json", "r", encoding="utf-8") as f:
            config = json.loads(f.read())
            return config


log = init_log()
config = load_config()
lock = asyncio.Lock()


print('\033[1;32;40m  _____   __   _   _____   _   _    _____  __    __ ' + '\033[0m')
print('\033[1;32;40m /  _  \\ |  \\ | | | ____| | | / /  | ____| \\ \\  / /' + '\033[0m')
print('\033[1;32;40m | | | | |   \\| | | |__   | |/ /   | |__    \\ \\/ /' + '\033[0m')
print('\033[1;32;40m | | | | | |\\   | |  __|  | |\\ \\   |  __|    \\  / ' + '\033[0m')
print('\033[1;32;40m | |_| | | | \\  | | |___  | | \\ \\  | |___    / /' + '\033[0m')
print('\033[1;32;40m \\_____/ |_|  \\_| |_____| |_|  \\_\\ |_____|  /_/' + '\033[0m')
log.info('作者ikun0014')
log.info('本项目基于wxy1343/ManifestAutoUpdate进行修改，采用GPL V3许可证')
log.info('版本：1.1.4')
log.info('项目仓库：https://github.com/ikunshare/Onekey')
log.debug('官网：ikunshare.com')
log.warning('本项目完全开源免费，如果你在淘宝，QQ群内通过购买方式获得，赶紧回去骂商家死全家\n交流群组：\n点击链接加入群聊【𝗶𝗸𝘂𝗻分享】：https://qm.qq.com/q/d7sWovfAGI\nhttps://t.me/ikunshare_group')


# 通过注册表获取Steam安装路径
def get_steam_path():
    key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, r'Software\Valve\Steam')
    steam_path = Path(winreg.QueryValueEx(key, 'SteamPath')[0])
    custom_steam_path = config["Custom_Steam_Path"]
    if not custom_steam_path == '':
        return Path(custom_steam_path)
    else:
        return steam_path


steam_path = get_steam_path()
isGreenLuma = any((steam_path / dll).exists() for dll in ['GreenLuma_2024_x86.dll', 'GreenLuma_2024_x64.dll', 'User32.dll'])
isSteamTools = (steam_path / 'config' / 'stplug-in').is_dir()


# 错误堆栈处理
def stack_error(exception):
    stack_trace = traceback.format_exception(type(exception), exception, exception.__traceback__)
    return ''.join(stack_trace)


# 从Steam API直接搜索游戏信息
async def search_game_info(search_term):
    async with ClientSession() as session:  
        url = f'https://steamui.com/loadGames.php?search={search_term}'
        async with session.get(url) as r:
            if r.status == 200:
                data = await r.json()
                games = data.get('games', [])
                return games
            else:
                log.error("⚠ 获取游戏信息失败")
                return []


# 通过游戏名查找appid
async def find_appid_by_name(game_name):
    games = await search_game_info(game_name)

    if games:
        log.info("🔍 找到以下匹配的游戏:")
        for idx, game in enumerate(games, 1):
            gamename = game['schinese_name'] if game['schinese_name'] else game['name']
            log.info(f"{idx}. {gamename} (AppID: {game['appid']})")

        while True:
            choice = input("请选择游戏编号：")
            if choice.isdigit() and 1 <= int(choice) <= len(games):
                selected_game = games[int(choice) - 1]
                log.info(f"✅ 选择的游戏: {selected_game['schinese_name']} (AppID: {selected_game['appid']})")
                return selected_game['appid'], selected_game['schinese_name']
            else:
                log.error(f"⚠ 错误的编号：{choice}，请重新输入。")

    return None, None


# 下载清单
async def get(sha, path, repo, session):
    url_list = [
        # f'https://gh.api.99988866.xyz/https://raw.githubusercontent.com/{repo}/{sha}/{path}',
        f'https://cdn.jsdmirror.com/gh/{repo}@{sha}/{path}',
        f'https://jsd.onmicrosoft.cn/gh/{repo}@{sha}/{path}',
        f'https://mirror.ghproxy.com/https://raw.githubusercontent.com/{repo}/{sha}/{path}',
        f'https://raw.githubusercontent.com/{repo}/{sha}/{path}',
        f'https://gh.jiasu.in/https://raw.githubusercontent.com/{repo}/{sha}/{path}'
    ]
    retry = 3
    while retry:
        for url in url_list:
            try:
                async with session.get(url, ssl=False) as r:
                    if r.status == 200:
                        return await r.read()
                    else:
                        log.error(f' 🔄 获取失败: {path} - 状态码: {r.status}')
            except ClientError:
                log.error(f' 🔄 获取失败: {path} - 连接错误')
        retry -= 1
        log.warning(f'  🔄  重试剩余次数: {retry} - {path}')
    log.error(f'  🔄 超过最大重试次数: {path}')
    raise Exception(f'  🔄 无法下载: {path}')


# 获取清单信息
async def get_manifest(sha, path, steam_path: Path, repo, session):
    collected_depots = []
    try:
        if path.endswith('.manifest'):
            depot_cache_path = steam_path / 'depotcache'
            if not depot_cache_path.exists():
                depot_cache_path.mkdir(exist_ok=True)
            save_path = depot_cache_path / path
            if save_path.exists():
                log.warning(f'👋已存在清单: {path}')
                return collected_depots
            content = await get(sha, path, repo, session)
            log.info(f' 🔄 清单下载成功: {path}')
            async with aiofiles.open(save_path, 'wb') as f:
                await f.write(content)
        elif path == 'Key.vdf':
            content = await get(sha, path, repo, session)
            log.info(f' 🔄 密钥下载成功: {path}')
            depots_config = vdf.loads(content.decode(encoding='utf-8'))
            for depot_id, depot_info in depots_config['depots'].items():
                collected_depots.append((depot_id, depot_info['DecryptionKey']))
    except Exception as e:
        log.error(f'处理失败: {path} - {stack_error(e)}')
        traceback.print_exc()
        raise
    return collected_depots


# 合并DecryptionKey
async def depotkey_merge(config_path, depots_config):
    if not config_path.exists():
        async with lock:
            log.error(' 👋 Steam默认配置不存在，可能是没有登录账号')
        return
    with open(config_path, encoding='utf-8') as f:
        config = vdf.load(f)
    software = config['InstallConfigStore']['Software']
    valve = software.get('Valve') or software.get('valve')
    steam = valve.get('Steam') or valve.get('steam')
    if 'depots' not in steam:
        steam['depots'] = {}
    steam['depots'].update(depots_config['depots'])
    with open(config_path, 'w', encoding='utf-8') as f:
        vdf.dump(config, f, pretty=True)
    return True


# 增加SteamTools解锁相关文件
async def stool_add(depot_data, app_id):
    lua_filename = f"Onekey_unlock_{app_id}.lua"
    lua_filepath = steam_path / "config" / "stplug-in" / lua_filename

    async with lock:
        log.info(f' ✅ SteamTools解锁文件生成: {lua_filepath}')
        with open(lua_filepath, "w", encoding="utf-8") as lua_file:
            lua_file.write(f'addappid({app_id}, 1, "None")\n')
            for depot_id, depot_key in depot_data:
                lua_file.write(f'addappid({depot_id}, 1, "{depot_key}")\n')

    luapacka_path = steam_path / "config" / "stplug-in" / "luapacka.exe"
    subprocess.run([str(luapacka_path), str(lua_filepath)])
    os.remove(lua_filepath)
    return True


# 增加GreenLuma解锁相关文件
async def greenluma_add(depot_id_list):
    app_list_path = steam_path / 'AppList'
    if app_list_path.exists() and app_list_path.is_file():
        app_list_path.unlink(missing_ok=True)
    if not app_list_path.is_dir():
        app_list_path.mkdir(parents=True, exist_ok=True)
    depot_dict = {}
    for i in app_list_path.iterdir():
        if i.stem.isdecimal() and i.suffix == '.txt':
            with i.open('r', encoding='utf-8') as f:
                app_id_ = f.read().strip()
                depot_dict[int(i.stem)] = None
                if app_id_.isdecimal():
                    depot_dict[int(i.stem)] = int(app_id_)
    for depot_id in depot_id_list:
        if int(depot_id) not in depot_dict.values():
            index = max(depot_dict.keys()) + 1 if depot_dict.keys() else 0
            if index != 0:
                for i in range(max(depot_dict.keys())):
                    if i not in depot_dict.keys():
                        index = i
                        break
            with (app_list_path / f'{index}.txt').open('w', encoding='utf-8') as f:
                f.write(str(depot_id))
            depot_dict[index] = int(depot_id)
    return True


async def check_github_api_rate_limit(headers, session):
    url = 'https://api.github.com/rate_limit'

    async with session.get(url, headers=headers, ssl=False) as r:
        if not r == None:
            r_json = await r.json()
        else:
            log.error('孩子，你怎么做到的？')
            os.system('pause')

    if r.status == 200:
        rate_limit = r_json['rate']
        remaining_requests = rate_limit['remaining']
        reset_time = rate_limit['reset']
        reset_time_formatted = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(reset_time))
        log.info(f' 🔄 剩余请求次数: {remaining_requests}')
    else:
        log.error('Github请求数检查失败')

    if remaining_requests == 0:
        log.warning(f' ⚠ GitHub API 请求数已用尽，将在 {reset_time_formatted} 重置, 不想等生成一个填配置文件里')


# 主函数
async def main(app_id, game_name):
    app_id_list = list(filter(str.isdecimal, app_id.strip().split('-')))
    app_id = app_id_list[0]
    
    async with ClientSession() as session:
        github_token = config["Github_Personal_Token"]
        headers = {'Authorization': f'Bearer {github_token}'} if github_token else None
        latest_date = None
        selected_repo = None

        # 检查Github API限额
        await check_github_api_rate_limit(headers, session)

        for repo in repos:
            url = f'https://api.github.com/repos/{repo}/branches/{app_id}'
            try:
                async with session.get(url, headers=headers, ssl=False) as r:
                    r_json = await r.json()
                    if 'commit' in r_json:
                        date = r_json['commit']['commit']['author']['date']
                        if latest_date is None or date > latest_date:
                            latest_date = date
                            selected_repo = repo
            except Exception as e:
                log.error(f' ⚠ 获取分支信息失败: {stack_error(e)}')
                traceback.print_exc()
        if selected_repo:
            log.info(f' 🔄 选择清单仓库：{selected_repo}')
            url = f'https://api.github.com/repos/{selected_repo}/branches/{app_id}'
            async with session.get(url, headers=headers, ssl=False) as r:
                r_json = await r.json()
                if 'commit' in r_json:
                    sha = r_json['commit']['sha']
                    url = r_json['commit']['commit']['tree']['url']
                    async with session.get(url, headers=headers, ssl=False) as r2:
                        r2_json = await r2.json()
                        if 'tree' in r2_json:
                            collected_depots = []
                            for i in r2_json['tree']:
                                result = await get_manifest(sha, i['path'], steam_path, selected_repo, session)
                                collected_depots.extend(result)
                            if collected_depots:
                                if isSteamTools:
                                    await stool_add(collected_depots, app_id)
                                    log.info(' ✅ 找到SteamTools，已添加解锁文件')
                                if isGreenLuma:
                                    await greenluma_add([app_id])
                                    depot_config = {'depots': {depot_id: {'DecryptionKey': depot_key} for depot_id, depot_key in collected_depots}}
                                    await depotkey_merge(steam_path / 'config' / 'config.vdf', depot_config)
                                    if await greenluma_add([int(i) for i in depot_config['depots'] if i.isdecimal()]):
                                        log.info(' ✅ 找到GreenLuma，已添加解锁文件')
                                log.info(f' ✅ 清单最后更新时间：{date}')
                                log.info(f' ✅ 入库成功: {app_id}：{game_name}')
                                os.system('pause')
                                return True
        log.error(f' ⚠ 清单下载或生成失败: {app_id}：{game_name}')
        os.system('pause')
        return False


repos = [
         'ManifestHub/ManifestHub',
         'ikun0014/ManifestHub',
         'Auiowu/ManifestAutoUpdate',
         'tymolu233/ManifestAutoUpdate'
        ]
if __name__ == '__main__':
    try:
        log.debug('App ID可以在SteamDB或Steam商店链接页面查看')
        user_input = input("请输入游戏AppID或名称：").strip()
        appid, game_name = asyncio.run(find_appid_by_name(user_input))
        if not appid:
            log.error(' ⚠ 未找到匹配的游戏，请尝试其他名称。')
        else:
            asyncio.run(main(appid, game_name))
    except KeyboardInterrupt:
        exit()
    except Exception as e:
        log.error(f' ⚠ 发生错误: {stack_error(e)}')
        traceback.print_exc()
    if not user_input:
        os.system('pause')
