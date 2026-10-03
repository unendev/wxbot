import llm_service
reply = llm_service.call_llm('remote_zima_test', '你好，测试一下DeepSeek响应')
print('ZIMABOARD DEEPSEEK TEST OK, REPLY LEN:', len(reply))
