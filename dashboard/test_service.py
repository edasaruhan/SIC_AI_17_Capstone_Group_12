"""Offline checks: all HTTP requests are mocked; no Gemini calls are made."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import requests
import service


class MessageErrorsTest(unittest.TestCase):
    def setUp(self):
        self.network_guard=patch('requests.sessions.Session.request', side_effect=AssertionError('Real network forbidden'))
        self.network_guard.start()
        self.addCleanup(self.network_guard.stop)

    def test_transport_categories_and_secret_redaction(self):
        for cls, category in [
            (requests.exceptions.Timeout,'Timeout'),
            (requests.exceptions.ConnectTimeout,'Timeout'),
            (requests.exceptions.ReadTimeout,'Timeout'),
            (requests.exceptions.SSLError,'SSLError'),
            (requests.exceptions.ProxyError,'ProxyError'),
            (requests.exceptions.ConnectionError,'ConnectionError'),
            (requests.exceptions.HTTPError,'HTTPError'),
            (requests.exceptions.InvalidHeader,'RequestException'),
        ]:
            with self.subTest(category=cls.__name__), patch('service.requests.post', side_effect=cls('SECRET-SENTINEL')) as post:
                with self.assertRaises(service.GenerationError) as caught:
                    service.request_message('test', 'SECRET-SENTINEL', 'test-model')
                self.assertIn(category,str(caught.exception))
                self.assertNotIn('SECRET-SENTINEL',str(caught.exception))
                self.assertEqual(post.call_count,1)
                self.assertTrue(post.call_args.kwargs['verify'])
                self.assertFalse(post.call_args.kwargs['allow_redirects'])
                config=post.call_args.kwargs['json']['generationConfig']
                self.assertEqual(config['maxOutputTokens'],2048)
                self.assertNotIn('safetySettings',post.call_args.kwargs['json'])

    def test_http_statuses_never_show_response_body(self):
        for code in [301,400,401,403,404,429,500,503]:
            response=Mock(status_code=code, text='SECRET-SENTINEL')
            with self.subTest(code=code), patch('service.requests.post',return_value=response) as post:
                with self.assertRaises(service.GenerationError) as caught:
                    service.request_message('test','test-key','test-model')
                self.assertIn(str(code),str(caught.exception))
                self.assertNotIn('SECRET-SENTINEL',str(caught.exception))
                response.json.assert_not_called()
                self.assertEqual(post.call_count,1)

    def test_invalid_json(self):
        response=Mock(status_code=200)
        response.json.side_effect=ValueError('SECRET-SENTINEL')
        with patch('service.requests.post',return_value=response):
            with self.assertRaisesRegex(service.GenerationError,'JSON') as caught:
                service.request_message('test','test-key','test-model')
            self.assertNotIn('SECRET-SENTINEL',str(caught.exception))

    def test_malformed_and_incomplete_responses(self):
        for payload in [None, [], {}, {'candidates':None}, {'candidates':[None]},
                        {'candidates':[{'content':{'parts':[{'text':12}]}}]},
                        {'candidates':[{'content':{'parts':[{'text':'draft'}]},'finishReason':'MAX_TOKENS'}]},
                        {'candidates':[{'content':{'parts':[{'text':'draft'}]}}], 'usageMetadata':{'totalTokenCount':'SECRET-SENTINEL'}}]:
            response=Mock(status_code=200)
            response.json.return_value=payload
            with self.subTest(payload=payload), patch('service.requests.post',return_value=response):
                with self.assertRaises(service.GenerationError) as caught:
                    service.request_message('test','test-key','test-model')
                self.assertIn('Yanıt işleme',str(caught.exception))
                self.assertNotIn('SECRET-SENTINEL',str(caught.exception))

    def test_cache_and_quota_with_mocked_success(self):
        response=Mock(status_code=200)
        response.json.return_value={'candidates':[{'content':{'parts':[{'text':'internal','thought':True},{'text':'Taslak'}]},'finishReason':'STOP'}], 'usageMetadata':{'totalTokenCount':7}}
        with tempfile.TemporaryDirectory() as directory, patch.object(service,'ROOT',Path(directory)), patch('service.requests.post',return_value=response) as post:
            self.assertEqual(service.generate('prompt','test-key','test-model',1),('Taslak',False,7))
            self.assertEqual(service.generate('prompt','test-key','test-model',1),('Taslak',True,None))
            with self.assertRaisesRegex(service.GenerationError,'sınırı'):
                service.generate('new prompt','test-key','test-model',1)
            self.assertEqual(post.call_count,1)

    def test_failed_request_is_counted_without_retry_or_cache(self):
        with tempfile.TemporaryDirectory() as directory, patch.object(service,'ROOT',Path(directory)), patch('service.requests.post',side_effect=requests.exceptions.ConnectionError('SECRET-SENTINEL')) as post:
            with self.assertRaises(service.GenerationError):
                service.generate('prompt','test-key','test-model',1)
            with service.connect() as db:
                self.assertEqual(db.execute('SELECT status FROM events').fetchall(),[('error',)])
                self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
            with self.assertRaisesRegex(service.GenerationError,'sınırı'):
                service.generate('prompt','test-key','test-model',1)
            self.assertEqual(post.call_count,1)

    def test_max_tokens_reports_safe_metadata_even_without_text(self):
        for parts in [[],[{'text':'PRIVATE-CUSTOMER-TEXT'}]]:
            payload={'candidates':[{'finishReason':'MAX_TOKENS','content':{'parts':parts}}],
                     'usageMetadata':{'promptTokenCount':30,'candidatesTokenCount':10,
                                      'thoughtsTokenCount':2038,'totalTokenCount':2078}}
            with self.assertRaises(service.GenerationError) as caught:
                service.parse_message(payload)
            message=str(caught.exception)
            self.assertIn('Çıktı token sınırına ulaşıldı',message)
            self.assertIn('finishReason=MAX_TOKENS',message)
            self.assertIn('promptFeedback.blockReason=bildirilmedi',message)
            for name,value in payload['usageMetadata'].items():
                self.assertIn(f'{name}={value}',message)
            self.assertNotIn('PRIVATE-CUSTOMER-TEXT',message)

    def test_block_reasons_and_missing_finish_never_cache(self):
        for finish,block in [('MAX_TOKENS',None),('SAFETY',None),('RECITATION',None),
                             ('OTHER',None),(None,None),('FINISH_REASON_UNSPECIFIED',None),
                             ('STOP','SAFETY'),('STOP','BLOCKLIST'),('STOP','UNKNOWN_PRIVATE_VALUE')]:
            payload={'candidates':[{'finishReason':finish,'content':{'parts':[{'text':'PRIVATE-CUSTOMER-TEXT'}]}}]}
            if block:payload['promptFeedback']={'blockReason':block}
            response=Mock(status_code=200)
            response.json.return_value=payload
            with self.subTest(finish=finish,block=block), tempfile.TemporaryDirectory() as directory, patch.object(service,'ROOT',Path(directory)), patch('service.requests.post',return_value=response) as post:
                with self.assertRaises(service.GenerationError) as caught:
                    service.generate('PRIVATE-CUSTOMER-TEXT','SECRET-SENTINEL','test-model',50)
                text=str(caught.exception)
                self.assertNotIn('PRIVATE-CUSTOMER-TEXT',text)
                self.assertNotIn('SECRET-SENTINEL',text)
                self.assertNotIn('UNKNOWN_PRIVATE_VALUE',text)
                with service.connect() as db:
                    self.assertEqual(db.execute('SELECT COUNT(*) FROM messages').fetchone()[0],0)
                    self.assertEqual(db.execute('SELECT status FROM events').fetchall(),[('error',)])
                self.assertEqual(post.call_count,1)

    def test_prompt_block_without_candidates(self):
        with self.assertRaises(service.GenerationError) as caught:
            service.parse_message({'promptFeedback':{'blockReason':'SAFETY','blockReasonMessage':'SECRET-SENTINEL'},'usageMetadata':{'promptTokenCount':42}})
        text=str(caught.exception)
        self.assertIn('güvenlik filtresi',text)
        self.assertIn('promptFeedback.blockReason=SAFETY',text)
        self.assertIn('promptTokenCount=42',text)
        self.assertNotIn('SECRET-SENTINEL',text)

    def test_diagnostics_only_allow_codes_and_integer_counts(self):
        for malicious in ['SECRET-SENTINEL',{'secret':'SECRET-SENTINEL'},['SECRET-SENTINEL'],True,-1,2**64,1.5]:
            payload={'candidates':[{'finishReason':malicious}],
                     'promptFeedback':{'blockReason':malicious},
                     'usageMetadata':{name:malicious for name in service.TOKEN_FIELDS}}
            text=service.response_details(payload)
            self.assertNotIn('SECRET-SENTINEL',text)
            for name in service.TOKEN_FIELDS:self.assertIn(f'{name}=geçersiz',text)

    def test_stop_with_empty_or_thought_only_content_rejected(self):
        for parts in [[],[{'text':'  '}],[{'text':'PRIVATE-THOUGHT','thought':True}]]:
            with self.assertRaises(service.GenerationError):
                service.parse_message({'candidates':[{'finishReason':'STOP','content':{'parts':parts}}]})

    def test_two_sentence_prompt_rule_preserved(self):
        import pandas as pd
        prompt=service.prompt_for(pd.DataFrame([{'PreferedOrderCat':'Fashion','Complain':0}]),{'action':'Etkileşim Mesajı'})
        self.assertIn('en fazla iki kısa cümle',prompt)


if __name__=='__main__':
    unittest.main()
