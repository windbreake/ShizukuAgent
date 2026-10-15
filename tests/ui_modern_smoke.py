"""Browser smoke: production build, isolated API fixtures, no live model calls."""
import json
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(__file__).resolve().parents[1]
SimpleHTTPRequestHandler.extensions_map['.js'] = 'application/javascript'
SimpleHTTPRequestHandler.extensions_map['.css'] = 'text/css'
class Handler(SimpleHTTPRequestHandler):
    def do_GET(self):
        if '.' not in self.path.rsplit('/',1)[-1]: self.path='/index.html'
        super().do_GET()
server = ThreadingHTTPServer(('127.0.0.1', 18765), partial(Handler, directory=str(root / 'frontend' / 'dist')))
threading.Thread(target=server.serve_forever, daemon=True).start()

def fixture(route):
    path = route.request.url.split('/api/', 1)[-1]
    payload = {'success': True}
    if path == 'agent/status': payload.update(personas=[{'skill_id':'shizuku','name':'Shizuku'}],default_persona='shizuku')
    elif path == 'model-groups': payload.update(default='default',groups={'default':{'name':'Default Agent','models':['primary']}})
    elif path == 'models': payload.update(models={'primary':{'model':'test','name':'Primary Agent Model','enabled':True,'capabilities':['chat'],'provider':'demo'}},providers={'demo':{'name':'Demo Provider','base_url':'https://example.com/v1'}})
    elif path == 'config': payload.update(providers={'demo':{'name':'Demo Provider','base_url':'https://example.com/v1'}},models={'primary':{'name':'Demo Model','model':'test','provider':'demo','capabilities':['chat']}},model_groups={'default':{'name':'Default','models':['primary']}},default_model_group='default')
    elif path == 'providers/discover': payload.update(models=[{'id':'model-a','name':'Model Alpha','owned_by':'vendor','context_length':200000},{'id':'model-b','owned_by':'vendor'}])
    elif path == 'work_mode/status': payload.update(enabled=False)
    elif path.startswith('workbench/files'): payload.update(root='test-workspace',entries=[])
    elif path == 'workbench/changes': payload.update(initialized=False,status='',diff='')
    elif path == 'chat': payload.update(persona='shizuku',reply='测试回复：请求已正确连接。',engine='fixture',active_model='test',trace=[])
    elif path.startswith('task-plan?'): payload.update(items=[{'content':'检查项目','status':'completed','priority':'high'},{'content':'验证修改','status':'in_progress','priority':'medium'}],running=True,run_id='fixture')
    elif path == 'gateway': payload.update(config={'host':'127.0.0.1','port':8888,'api_enabled':True,'websocket_enabled':False},current={'host':'127.0.0.1','port':8888},message='网关设置已保存')
    elif path == 'personas': payload.update(personas=[{'filename':'shizuku.json','name':'Shizuku','is_active':True},{'filename':'alice.json','name':'Alice','is_active':False}])
    elif path == 'record-groups?query=': payload.update(items=[{'persona':'shizuku','total':25},{'persona':'alice','total':1}])
    elif path.startswith('persona-records?'):
        from urllib.parse import parse_qs
        params=parse_qs(path.split('?',1)[1]); persona=params['persona'][0]; page=int(params['page'][0])
        payload.update(items=[{'id':page,'persona':persona,'role':'user','content':f'{persona} page {page}','created_at':'2026-10-15'}],total=25 if persona=='shizuku' else 1,page=page)
    elif path == 'logs':
        route.fulfill(status=200,content_type='text/plain',body='[INFO] ready\n[WARNING] slow\n[ERROR] failed\n[DEBUG] details\n' + '[INFO] normal line\n'*100)
        return
    elif path.startswith('settings-resources/document'):
        payload.update(content='{"servers": []}',name='servers.json')
    elif path == 'settings-resources/tts': payload.update(items=[{'id':'voice-demo','name':'Voice Demo','files':3}],selected='voice-demo')
    elif path.startswith('agent/memory/long_term'): payload.update(long_term='测试记忆')
    else: payload.update(data=[],items=[],plugins=[])
    route.fulfill(status=200,content_type='application/json',body=json.dumps(payload))

with sync_playwright() as p:
    browser=p.chromium.launch()
    page=browser.new_page(viewport={'width':1440,'height':1000})
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.route('**/api/**',fixture)
    page.goto('http://127.0.0.1:18765/')
    page.wait_for_timeout(1000)
    page.get_by_role('heading',name='从一个想法开始').wait_for(timeout=5000)
    assert 'Primary Agent Model' not in page.locator('.composer').inner_text()
    assert 'test' in page.get_by_role('button',name='模型',exact=True).inner_text()
    def assert_panels():
        chat=page.locator('.chat-col').bounding_box()
        files=page.locator('.workspace-panel').bounding_box()
        assert chat['width'] > 450,chat
        assert abs(chat['y']-files['y']) < 3,(chat,files)
        assert files['x'] >= chat['x']+chat['width'],(chat,files)
        assert abs(chat['height']-files['height']) < 3,(chat,files)
    assert_panels()
    for width in [280, 360]:
        panel = page.locator('.workspace-panel')
        panel.evaluate('(el,width)=>{el.style.width=width+"px";el.style.justifySelf="end"}', width)
        opener = page.get_by_role('button',name='打开方式',exact=True)
        assert opener.locator('.ui-select-label').evaluate('(el)=>getComputedStyle(el).whiteSpace') == 'nowrap'
        assert opener.evaluate('(el)=>el.scrollHeight <= el.clientHeight + 2')
        assert panel.evaluate('(el)=>el.scrollWidth <= el.clientWidth + 2')
        assert page.locator('.workspace-panel header button').first.evaluate('(el)=>el.scrollHeight <= el.clientHeight + 2')
    page.locator('.workspace-panel').evaluate('(el)=>{el.style.width="";el.style.justifySelf=""}')
    for search in page.locator('.search-field input').all():
        assert search.evaluate('(el)=>getComputedStyle(el).backgroundColor') == 'rgba(0, 0, 0, 0)'
    composer = page.locator('.composer').bounding_box()
    textarea = page.locator('.composer textarea').bounding_box()
    toolbar = page.locator('.composer-toolbar').bounding_box()
    assert textarea['width'] > composer['width'] * .85, (composer,textarea)
    assert abs(textarea['x'] - toolbar['x']) < 12, (textarea,toolbar)
    assert toolbar['y'] > textarea['y'], (textarea,toolbar)
    assert page.locator('.composer select').count() == 0
    page.get_by_role('button',name='隐藏或显示会话列表',exact=True).click()
    assert page.locator('.sessions').is_hidden()
    assert_panels()
    page.get_by_role('button',name='隐藏或显示会话列表',exact=True).click()
    grip=page.get_by_role('separator',name='调整会话栏宽度').bounding_box()
    initial=page.locator('.sessions').bounding_box()['width']
    page.mouse.move(grip['x']+3,grip['y']+50);page.mouse.down();page.mouse.move(grip['x']+63,grip['y']+50);page.mouse.up()
    assert page.locator('.sessions').bounding_box()['width'] > initial+30
    assert_panels()
    page.get_by_title('收起或展开右侧栏').click()
    assert page.locator('.workspace-panel').count()==0
    page.get_by_role('button',name='隐藏或显示会话列表',exact=True).click()
    assert page.locator('.sessions').count()==0
    assert page.locator('.chat-col').bounding_box()['width'] > 1300
    page.get_by_role('button',name='隐藏或显示会话列表',exact=True).click()
    page.get_by_title('收起或展开右侧栏').click()
    assert_panels()
    page.get_by_role('button',name='打开方式',exact=True).click()
    page.get_by_role('option',name='VS Code',exact=True).click()
    assert 'VS Code' in page.get_by_role('button',name='打开方式',exact=True).inner_text()
    assert composer['height'] < 250, composer
    for box in page.locator('.composer svg').all():
        rect = box.bounding_box()
        assert rect['width'] <= 24 and rect['height'] <= 24, rect
    page.get_by_role('button',name='切换深色主题').click()
    assert page.locator('html').get_attribute('data-theme')=='dark'
    page.reload()
    assert page.locator('html').get_attribute('data-theme')=='dark'
    page.get_by_role('button',name='切换浅色主题').click()
    page.get_by_role('button',name='模型',exact=True).click()
    page.get_by_role('textbox',name='搜索模型',exact=True).fill('missing')
    page.get_by_text('没有匹配项',exact=True).wait_for()
    page.keyboard.press('Escape')
    page.get_by_role('button',name='工作模式',exact=True).click()
    page.get_by_role('button',name='完全控制',exact=True).click()
    password_dialog = page.get_by_role('dialog')
    password_dialog.wait_for()
    assert password_dialog.get_by_label('安全密码').evaluate('(el)=>document.activeElement===el')
    page.keyboard.press('Escape')
    password_dialog.wait_for(state='hidden')
    page.get_by_role('button',name='添加上下文或命令').click()
    menu=page.get_by_role('menu').bounding_box()
    plus=page.get_by_role('button',name='添加上下文或命令').bounding_box()
    assert menu['y']+menu['height'] < plus['y'],(menu,plus)
    page.get_by_role('button',name='命令 /',exact=True).click()
    page.get_by_role('button',name='/new · 新会话',exact=True).wait_for()
    page.keyboard.press('Escape')
    page.locator('.composer textarea').fill('')
    page.get_by_role('button',name='分析项目',exact=True).click()
    assert '项目' in page.locator('.composer textarea').input_value()
    page.locator('.composer textarea').fill('界面连通性测试')
    page.get_by_role('button',name='发送',exact=True).click()
    page.locator('.bubble').filter(has_text='测试回复：请求已正确连接。').wait_for()
    page.get_by_role('button',name='已完成 1 个任务（共 2 个）',exact=False).wait_for()
    assert page.locator('.plan-item.completed').count()==1
    page.locator('.task-plan-heading').click()
    assert page.locator('.task-plan-list').count()==0
    page.locator('.task-plan-heading').click()
    page.screenshot(path=str(root/'data'/'ui-modern-light.png'),full_page=True)
    page.get_by_role('button',name='切换深色主题').click()
    page.screenshot(path=str(root/'data'/'ui-modern-dark.png'),full_page=True)
    page.get_by_role('link',name='设置',exact=True).click()
    page.get_by_role('button',name='MCP 集成',exact=True).click()
    page.locator('.setting-section>summary').filter(has_text='MCP 服务器').wait_for()
    assert page.locator('.setting-section>summary').filter(has_text='技能策略').is_hidden()
    mcp_section=page.locator('.setting-section').filter(has=page.locator('summary').filter(has_text='MCP 服务器'))
    mcp_section.locator(':scope>summary').click()
    assert mcp_section.get_by_role('button',name='编辑 JSON',exact=True).is_hidden()
    mcp_section.locator(':scope>summary').click()
    page.get_by_role('button',name='编辑 JSON',exact=True).click()
    page.get_by_role('dialog',name='编辑源文件').wait_for()
    assert 'servers' in page.get_by_role('textbox',name='文件内容').input_value()
    page.get_by_role('button',name='取消',exact=True).click()
    page.get_by_role('button',name='全部设置',exact=True).click()
    assert page.get_by_text('命令执行',exact=True).count()==0
    assert page.get_by_text('沙箱审批',exact=True).count()==0
    assert page.get_by_text('辅助模型',exact=True).count()==0
    page.get_by_text('导入 ZIP',exact=True).wait_for()
    for label in ['提供商与模型组','模型配置与辅助 API','安全与权限','对话记录与存储','用量与资源监控','运行日志','连接诊断','连接网关','技能市场与本机智能体']:
        page.get_by_role('link',name=label,exact=True).click()
        page.wait_for_timeout(650)
        if label == '对话记录与存储':
            page.locator('.persona-records>summary').filter(has_text='Shizuku').click()
            page.get_by_text('shizuku page 1',exact=True).wait_for()
            page.get_by_role('button',name='下一页',exact=True).first.click()
            page.get_by_text('shizuku page 2',exact=True).wait_for()
        if label == '运行日志':
            page.locator('.log-line.error').wait_for()
            terminal=page.locator('.log-terminal')
            assert terminal.evaluate('(el)=>el.scrollHeight>el.clientHeight')
            page.get_by_role('button',name='错误',exact=False).click()
            assert page.locator('.log-line').count()==1
            assert page.locator('.log-line.error').count()==1
            assert terminal.bounding_box()['height'] < page.viewport_size['height']
            page.get_by_role('button',name='全部',exact=False).click()
        if label == '连接网关':
            page.get_by_label('监听端口',exact=True).fill('9001')
            with page.expect_request(lambda r:'/api/gateway' in r.url and r.method=='PUT') as gateway_saved:
                page.get_by_role('button',name='保存网关设置',exact=True).click()
            assert gateway_saved.value.post_data_json['port']==9001
        if label == '模型配置与辅助 API':
            field = page.locator('.registry-card:visible .field-grid label').first
            assert field.evaluate('(el)=>getComputedStyle(el).flexDirection') == 'column'
            assert page.locator('.config-form>.panel:visible').count() == 1
            page.screenshot(path=str(root/'data'/'ui-config-modern.png'),full_page=True)
            page.get_by_role('button',name='模型',exact=False).filter(has_text='模型').count()
            page.locator('.config-sections button').nth(1).click()
            page.get_by_label('模型显示名').fill('Edited Model')
            page.get_by_role('button',name='保存更改',exact=True).click()
            page.get_by_role('button',name='保存更改',exact=True).wait_for()
    page.get_by_role('button',name='运行观测',exact=True).click(timeout=5000)
    page.get_by_role('button',name='刷新状态',exact=True).click()
    page.get_by_role('link',name='提供商与模型组',exact=True).click()
    page.get_by_role('link',name='添加提供商',exact=True).click()
    page.get_by_role('heading',name='添加提供商',exact=True).wait_for()
    page.locator('.provider-editor input').first.fill('ui-provider')
    page.get_by_label('名称',exact=True).fill('UI Provider')
    page.get_by_label('Base URL',exact=True).fill('https://example.com/v1')
    page.get_by_role('button',name='获取模型列表',exact=True).click()
    page.get_by_role('dialog',name='选择模型').wait_for()
    page.wait_for_timeout(300)
    dialog_style = page.get_by_role('dialog',name='选择模型').evaluate('(el)=>({background:getComputedStyle(el).backgroundColor,opacity:getComputedStyle(el).opacity})')
    assert dialog_style['background'] != 'rgba(0, 0, 0, 0)', dialog_style
    assert dialog_style['opacity'] == '1', dialog_style
    for theme in ['light', 'dark']:
        page.locator('html').evaluate('(el,theme)=>el.dataset.theme=theme', theme)
        assert page.get_by_role('dialog',name='选择模型').evaluate('(el)=>getComputedStyle(el).backgroundColor') == ('rgb(255, 255, 255)' if theme == 'light' else 'rgb(34, 37, 43)')
        page.screenshot(path=str(root/'data'/f'ui-model-dialog-{theme}.png'),full_page=True)
    page.get_by_text('200K',exact=True).wait_for()
    page.get_by_role('searchbox',name='搜索模型…',exact=True).fill('Alpha')
    assert page.get_by_role('checkbox',name='model-b',exact=True).count()==0
    page.get_by_role('checkbox',name='model-a',exact=True).check()
    page.get_by_role('searchbox',name='搜索模型…',exact=True).fill('')
    page.get_by_role('checkbox',name='只看已选',exact=True).check()
    assert page.get_by_role('checkbox',name='model-b',exact=True).count()==0
    page.get_by_role('button',name='应用',exact=True).click()
    assert page.locator('.header-row input').first.input_value() == 'model-a'
    page.screenshot(path=str(root/'data'/'ui-provider-editor.png'),full_page=True)
    with page.expect_request(lambda r:'/api/providers/ui-provider' in r.url and r.method=='PUT') as saved:
        page.get_by_role('button',name='保存',exact=True).click()
    assert saved.value.post_data_json['models']==['model-a']
    assert saved.value.post_data_json['model_names']=={'model-a':'Model Alpha'}
    assert not errors,errors
    browser.close()
server.shutdown()
print('PASS: themes, persistence, composer, chat, settings filters, 9 management routes, observation; zero page errors')
