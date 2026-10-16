import copy
import unittest
from app.context_manager import prepare, scope, read_state
from test_agent_graph import FakeStorage


class ContextTests(unittest.TestCase):
    def test_compaction_preserves_originals_and_reuses_summary(self):
        storage=FakeStorage();calls=[]
        history=[{'role':'system','content':'Persona Alice'}]
        for i in range(10):
            history.extend([{'role':'user','content':f'goal {i}'},{'role':'assistant','content':'details '*300}])
        original=copy.deepcopy(history)
        storage.save_checkpoint('a','alice',{'messages':original})
        def summarize(messages,model):
            calls.append(messages)
            self.assertEqual([],model['tools'])
            self.assertFalse(model['stream'])
            return {'content':'目标：继续实现；约束：保留人格；发现：已读文件；待办：测试。'}
        model={'id':'test','context_window':16000}
        with scope(storage,'a','alice'):
            view=prepare(history,model,summarize,True)
            self.assertLess(len(view),len(history))
            self.assertIn('Persona Alice',view[0]['content'])
            self.assertTrue(any('goal 9'==m['content'] for m in view))
            first=len(calls)
            prepare(history,model,summarize)
            self.assertEqual(first,len(calls))
            self.assertTrue(read_state()['compaction']['summary'])
            self.assertEqual(original,storage.load_checkpoint('a','alice')['messages'])
            # Revert before the summarized boundary invalidates that summary.
            view=prepare(history[:3],model,summarize)
            self.assertFalse(any('会话压缩摘要' in m['content'] for m in view))

    def test_failure_does_not_destroy_original_history(self):
        storage=FakeStorage();messages=[{'role':'user','content':str(i)} for i in range(5)]
        storage.save_checkpoint('a','p',{'messages':messages})
        with scope(storage,'a','p'),self.assertRaises(RuntimeError):
            prepare(messages,{'id':'t'},lambda m,c:{'content':''},True)
        self.assertEqual(messages,storage.load_checkpoint('a','p')['messages'])

    def test_automatic_compaction_keeps_tool_pairs_and_latest_request(self):
        messages=[]
        for i in range(8):
            messages.extend([{'role':'user','content':f'task {i}'},{'role':'assistant','content':'x'*8000}])
        messages.extend([{'role':'user','content':'continue latest'}, {'role':'assistant','content':'','tool_calls':[{'id':'call','type':'function','function':{'name':'read_file','arguments':'{}'}}]}, {'role':'tool','tool_call_id':'call','content':'latest tool result'}])
        storage=FakeStorage();calls=[]
        with scope(storage,'auto','p'):
            view=prepare(messages,{'context_window':16000},lambda m,c:(calls.append(m) or {'content':'目标与已完成工作摘要'}))
            self.assertTrue(calls)
            self.assertEqual(messages[-3:],view[-3:])
            self.assertLess(read_state()['estimated_tokens'],16000)

    def test_single_oversized_turn_reports_budget_error(self):
        with self.assertRaisesRegex(RuntimeError,'超过模型上下文预算'):
            prepare([{'role':'user','content':'大'*20000}],{'context_window':4096},lambda m,c:{'content':'summary'})
