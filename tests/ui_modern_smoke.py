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
    elif path.startswith('workbench/context'):
        payload.update(context={'model':'fixture-model','provider':'demo','context_limit':32768,'estimated_tokens':2048,'usage_percent':6.3,'request_messages':[{'role':'system','content':'人格约束'},{'role':'user','content':'上下文查看测试'}],'compaction':{'summary':'目标：保留任务上下文。','count':4}},messages=[{'id':'original1','role':'user','content':'上下文查看测试'}],message_count=1,parts={'user':100,'assistant':200,'tool':300,'system':400},user_messages=1,assistant_messages=0)
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
    assert page.locator('.chat-col>.pane-head button').count()==1
    assert page.locator('.titlebar .sidebar-toggle').count()==2
    theme_box=page.locator('.theme-toggle').bounding_box()
    assert page.locator('.titlebar .sidebar-toggle').first.bounding_box()['x']>theme_box['x']
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
    # Resize a mounted workbench, including saved oversized panes and usable drawers.
    for width,height in [(1920,1080),(1280,720),(1024,768),(820,700),(390,844),(320,568),(844,390)]:
        page.set_viewport_size({'width':width,'height':height})
        page.wait_for_timeout(120)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'),(width,height)
        chat=page.locator('.chat-col').bounding_box()
        assert chat['width'] >= min(550,width-28),(width,chat)
        for selector in ['.composer','.composer-toolbar','.composer-toolbar>.send']:
            box=page.locator(selector).bounding_box()
            assert box['x']>=chat['x'] and box['x']+box['width']<=chat['x']+chat['width']+1,(width,selector,box,chat)
            assert box['y']+box['height']<=height,(width,height,selector,box)
        assert page.locator('.chat-col>.pane-body').bounding_box()['height']>60,(width,height)
        for label in ['模型','强度','人格','工作模式']:
            page.get_by_role('button',name=label,exact=True).click()
            popup=page.locator('.composer-toolbar .composer-popover').bounding_box()
            assert popup['x']>=0 and popup['x']+popup['width']<=width and popup['y']>=0,(width,height,label,popup)
            page.keyboard.press('Escape')
            page.locator('.composer-toolbar .composer-popover').wait_for(state='detached')
        if width<1180:
            page.get_by_title('收起或展开右侧栏').click()
            panel=page.locator('.workspace-panel')
            assert panel.is_visible()
            assert panel.evaluate('(el)=>el.scrollWidth<=el.clientWidth+2')
            page.keyboard.press('Escape')
            assert panel.count()==0
        if width<900:
            page.get_by_role('button',name='隐藏或显示会话列表',exact=True).click()
            assert page.locator('.sessions').is_visible()
            page.get_by_role('button',name='关闭侧栏',exact=True).click(position={'x':width-15,'y':30})
            assert page.locator('.sessions').count()==0
    page.set_viewport_size({'width':1440,'height':1000})
    page.wait_for_timeout(120)
    assert_panels()
    page.get_by_role('button',name='模型',exact=True).click()
    page.get_by_role('textbox',name='搜索模型',exact=True).fill('missing')
    page.get_by_text('没有匹配项',exact=True).wait_for()
    page.keyboard.press('Escape')
    page.get_by_role('button',name='工作模式',exact=True).click()
    page.get_by_role('button',name='完全控制',exact=True).click()
    password_dialog = page.get_by_role('dialog')
    password_dialog.wait_for()
    page.wait_for_timeout(250)
    dialog_box=password_dialog.bounding_box()
    assert dialog_box['width']<=480 and abs(dialog_box['x']+dialog_box['width']/2-720)<3,dialog_box
    assert abs(dialog_box['y']+dialog_box['height']/2-500)<3,dialog_box
    assert password_dialog.get_by_label('安全密码').evaluate('(el)=>document.activeElement===el')
    assert password_dialog.evaluate('(el)=>el.matches(":modal")')
    for width,height in [(390,844),(320,568),(844,390)]:
        page.set_viewport_size({'width':width,'height':height})
        box=password_dialog.bounding_box()
        assert box['x']>=0 and box['y']>=0 and box['x']+box['width']<=width and box['y']+box['height']<=height,box
        assert password_dialog.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
    page.set_viewport_size({'width':1440,'height':1000})
    page.screenshot(path=str(root/'data'/'ui-mode-warning.png'))
    page.keyboard.press('Escape')
    password_dialog.wait_for(state='hidden')
    page.get_by_role('button',name='添加上下文或命令').click()
    menu=page.get_by_role('menu').bounding_box()
    plus=page.get_by_role('button',name='添加上下文或命令').bounding_box()
    assert menu['y']+menu['height'] < plus['y'],(menu,plus)
    page.get_by_role('button',name='命令 /',exact=True).click()
    page.get_by_role('option',name='/new · 新会话',exact=True).wait_for()
    command_dialog=page.get_by_role('dialog',name='命令面板')
    page.wait_for_timeout(250)
    box=command_dialog.bounding_box()
    composer_box=page.locator('.composer-surface').bounding_box()
    assert box['y']+box['height']<=composer_box['y']-3,(box,composer_box)
    assert abs(box['x']-composer_box['x'])<2,(box,composer_box)
    assert abs(box['width']-composer_box['width'])<2,(box,composer_box)
    page.get_by_role('textbox',name='搜索命令',exact=True).fill('compact')
    assert page.get_by_role('option',name='/compact · 压缩上下文',exact=True).get_attribute('aria-disabled')=='true'
    page.get_by_role('textbox',name='搜索命令',exact=True).fill('不存在的命令')
    page.get_by_text('没有匹配的命令',exact=True).wait_for()
    page.keyboard.press('Escape')
    for width,height in [(390,844),(320,568),(844,390),(1440,1000)]:
        page.set_viewport_size({'width':width,'height':height})
        page.locator('.composer textarea').fill('/files')
        popup=page.get_by_role('dialog',name='命令面板')
        popup.wait_for()
        rect=popup.bounding_box()
        assert rect['x']>=0 and rect['y']>=0 and rect['x']+rect['width']<=width and rect['y']+rect['height']<=height,(width,height,rect)
        assert popup.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
        page.get_by_role('option',name='/files · 文件侧栏',exact=True).click()
        assert page.locator('.workspace-panel').is_visible()
        assert popup.is_hidden()
        assert page.locator('.composer textarea').input_value()==''
        page.keyboard.press('Escape')
    page.locator('.composer textarea').fill('/context')
    page.keyboard.press('Enter')
    page.get_by_role('dialog',name='上下文',exact=True).wait_for()
    page.keyboard.press('Escape')
    page.keyboard.press('Control+k')
    page.screenshot(path=str(root/'data'/'ui-slash-commands.png'))
    page.keyboard.press('Escape')
    page.locator('.composer textarea').fill('保留草稿')
    page.keyboard.press('Control+k')
    page.get_by_role('textbox',name='搜索命令',exact=True).fill('context')
    page.keyboard.press('ArrowDown')
    page.keyboard.press('Enter')
    page.get_by_role('dialog',name='上下文',exact=True).wait_for()
    assert page.locator('.composer textarea').input_value()=='保留草稿'
    page.keyboard.press('Escape')
    page.locator('.composer textarea').fill('')
    page.get_by_role('button',name='分析项目',exact=True).click()
    assert '项目' in page.locator('.composer textarea').input_value()
    page.locator('.composer textarea').fill('界面连通性测试')
    page.get_by_role('button',name='发送',exact=True).click()
    page.locator('.bubble').filter(has_text='测试回复：请求已正确连接。').wait_for()
    compact_history=[{'id':'u-compact','role':'user','content':'界面连通性测试'},{'id':'c-compact','role':'assistant','kind':'compaction','status':'completed','content':'上下文压缩完成 · 估算 8000 → 2000 tokens\n\n目标：继续任务。'}]
    page.route('**/api/workbench/session?*',lambda route:route.fulfill(json={'success':True,'messages':compact_history}))
    pending_compaction=[]
    page.route('**/api/workbench/context/compact',lambda route:pending_compaction.append(route))
    page.locator('.composer textarea').fill('/compact')
    page.keyboard.press('Enter')
    page.locator('.thread .bubble').filter(has_text='正在压缩上下文…').wait_for()
    assert page.get_by_role('dialog',name='上下文',exact=True).is_hidden()
    assert len(pending_compaction)==1
    pending_compaction.pop().fulfill(json={'success':True})
    page.locator('.bubble').filter(has_text='上下文压缩完成').wait_for()
    page.get_by_text('上下文压缩 · /compact',exact=True).wait_for()
    page.unroute('**/api/workbench/context/compact')
    page.unroute('**/api/workbench/session?*')
    held=[]
    def hold_chat(route): held.append(route)
    page.route('**/api/chat',hold_chat)
    page.locator('.composer textarea').fill('队列第一条')
    page.get_by_role('button',name='发送',exact=True).click()
    page.wait_for_timeout(200)
    assert page.locator('.composer-toolbar>.send').count()==1
    stop=page.get_by_role('button',name='中止回复',exact=True)
    stop.wait_for()
    before_hover=stop.evaluate('(el)=>getComputedStyle(el).backgroundColor')
    stop.hover()
    assert stop.evaluate('(el)=>getComputedStyle(el).backgroundColor')==before_hover
    page.locator('.composer textarea').fill('队列第二条')
    assert page.locator('.composer-toolbar>.send').count()==1
    assert page.get_by_role('button',name='中止回复',exact=True).count()==0
    page.get_by_role('button',name='加入队列',exact=True).click()
    page.locator('.queue-text').filter(has_text='队列第二条').wait_for()
    assert len(held)==1
    page.locator('.composer textarea').fill('保留未发送草稿')
    held[0].fulfill(status=200,content_type='application/json',body=json.dumps({'success':True,'reply':'第一条完成','trace':[]}))
    page.wait_for_timeout(300)
    assert len(held)==2
    assert held[1].request.post_data_json['message']=='队列第二条'
    assert page.locator('.composer textarea').input_value()=='保留未发送草稿'
    held[1].fulfill(status=200,content_type='application/json',body=json.dumps({'success':True,'reply':'第二条完成','trace':[]}))
    page.locator('.bubble').filter(has_text='第二条完成').wait_for()
    page.unroute('**/api/chat',hold_chat)
    # The final answer must render even while the post-run Git request is held.
    changes_held=[]
    changes_count=[0]
    def hold_final_changes(route):
        changes_count[0]+=1
        if changes_count[0]==1:fixture(route)
        else:changes_held.append(route)
    page.route('**/api/workbench/changes',hold_final_changes)
    long_reply='完整输出开头\n\n'+('这是长回复正文，用来验证完成后的显示与滚动。\n\n'*150)+'完整输出结尾标记'
    def long_chat(route):route.fulfill(status=200,content_type='application/json',body=json.dumps({'success':True,'reply':long_reply,'trace':[]}))
    page.route('**/api/chat',long_chat)
    page.locator('.composer textarea').fill('测试完整输出')
    page.get_by_role('button',name='发送',exact=True).click()
    final=page.locator('.msg.agent .bubble').last
    final.filter(has_text='完整输出结尾标记').wait_for()
    page.wait_for_timeout(150)
    assert changes_held,'Post-run Git request should still be pending'
    assert page.locator('.execution-feed').count()==0
    assert page.locator('.chat-col>.pane-body').evaluate('(el)=>el.scrollHeight-el.clientHeight-el.scrollTop<5')
    for route in changes_held:fixture(route)
    page.unroute('**/api/workbench/changes',hold_final_changes)
    page.unroute('**/api/chat',long_chat)
    page.get_by_role('button',name='查看上下文',exact=True).click()
    context_dialog=page.get_by_role('dialog',name='上下文',exact=True)
    context_dialog.wait_for()
    assert context_dialog.evaluate('(el)=>el.matches(":modal")')
    context_dialog.get_by_text('fixture-model',exact=True).wait_for()
    context_dialog.get_by_role('button',name='原始消息',exact=True).click()
    context_dialog.get_by_text('user · original1',exact=False).wait_for()
    context_dialog.get_by_role('button',name='压缩上下文',exact=True).click()
    context_dialog.get_by_text('目标：保留任务上下文。',exact=True).wait_for()
    page.keyboard.press('Escape')
    context_dialog.wait_for(state='hidden')
    page.locator('.composer textarea').fill('/missing-command')
    page.get_by_role('button',name='发送',exact=True).click()
    page.locator('.toast-message').filter(has_text='未知命令').wait_for()
    assert page.locator('.composer-wrap .notice-error').count()==0
    page.locator('.toast-message').filter(has_text='未知命令').wait_for(state='detached',timeout=4500)
    page.keyboard.press('Escape')
    page.locator('.composer textarea').fill('')
    page.get_by_role('button',name='已完成 1 个任务（共 2 个）',exact=False).wait_for()
    assert page.locator('.plan-item.completed').count()==1
    page.locator('.task-plan-heading').click()
    assert page.locator('.task-plan-list').count()==0
    page.locator('.task-plan-heading').click()
    page.screenshot(path=str(root/'data'/'ui-modern-light.png'),full_page=True)
    page.get_by_role('button',name='切换深色主题').click()
    page.screenshot(path=str(root/'data'/'ui-modern-dark.png'),full_page=True)
    deleted_sessions=[]
    def delete_fixture(route):
        if route.request.method=='DELETE':
            deleted_sessions.append(route.request.post_data_json)
            route.fulfill(status=200,content_type='application/json',body=json.dumps({'success':True,'records':6}))
        else:fixture(route)
    page.route('**/api/workbench/session',delete_fixture)
    session_count=page.locator('.session-row').count()
    page.locator('.session-row').first.hover()
    page.locator('.session-delete').first.click()
    confirmation=page.get_by_role('dialog',name='删除此会话？')
    confirmation.wait_for()
    assert confirmation.evaluate('(el)=>el.matches(":modal")')
    for width,height in [(1440,1000),(390,844),(320,568),(844,390)]:
        page.set_viewport_size({'width':width,'height':height})
        box=confirmation.bounding_box()
        assert abs(box['x']+box['width']/2-width/2)<2 and abs(box['y']+box['height']/2-height/2)<2,box
        assert box['width']<=440 and box['y']>=0 and box['y']+box['height']<=height,box
        assert confirmation.evaluate('(el)=>el.scrollWidth<=el.clientWidth+1')
    page.set_viewport_size({'width':1440,'height':1000})
    page.screenshot(path=str(root/'data'/'ui-delete-confirmation.png'))
    page.keyboard.press('Escape')
    confirmation.wait_for(state='hidden')
    assert not deleted_sessions
    page.locator('.session-row').first.hover()
    page.locator('.session-delete').first.click()
    page.get_by_role('dialog',name='删除此会话？').get_by_role('button',name='确认',exact=True).click()
    page.wait_for_timeout(250)
    assert len(deleted_sessions)==1 and deleted_sessions[0]['thread_id']
    assert page.locator('.session-row').count()==session_count-1
    assert page.locator('.bubble').count()==0
    assert len(json.loads(page.evaluate('localStorage.getItem("sc_sessions")')))==session_count-1
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
    page.wait_for_timeout(250)
    editor_box=page.get_by_role('dialog',name='编辑源文件').bounding_box()
    assert abs(editor_box['x']+editor_box['width']/2-720)<3,editor_box
    assert abs(editor_box['y']+editor_box['height']/2-500)<3,editor_box
    assert 'servers' in page.get_by_role('textbox',name='文件内容').input_value()
    page.get_by_role('button',name='取消',exact=True).click()
    page.get_by_role('button',name='新增服务器',exact=True).click()
    page.get_by_role('dialog',name='新增 MCP 服务器').wait_for()
    page.get_by_role('dialog',name='新增 MCP 服务器').get_by_role('button',name='关闭弹窗').click()
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
            switch_style=page.get_by_role('switch',name='启用 API 连接').evaluate('(el)=>({width:getComputedStyle(el).width,height:getComputedStyle(el).height,radius:getComputedStyle(el).borderRadius,thumb:getComputedStyle(el,"::after").backgroundColor})')
            assert switch_style=={'width':'24px','height':'16px','radius':'4px','thumb':'rgb(255, 255, 255)'},switch_style
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
