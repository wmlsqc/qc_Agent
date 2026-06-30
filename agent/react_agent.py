from langchain.agents import create_agent
from model.factory import chat_model
from utils.prompt_loader import load_system_prompts
from agent.tools.agent_tools import (rag_summarize, get_weather, get_user_location, get_user_id,
                                     get_current_month, fetch_external_data, fill_context_for_report,
                                     get_model_info, get_robot_status, get_consumable_status,
                                     get_cleaning_history, diagnose_fault, get_user_profile,
                                     get_agent_diagnostics)
from agent.tools.middleware import monitor_tool, log_before_model, report_prompt_switch


class ReactAgent:
    def __init__(self):
        self.agent = create_agent(
            model=chat_model,
            system_prompt=load_system_prompts(),
            tools=[rag_summarize, get_weather, get_user_location, get_user_id,
                   get_current_month, fetch_external_data, fill_context_for_report,
                   get_model_info, get_robot_status, get_consumable_status,
                   get_cleaning_history, diagnose_fault, get_user_profile,
                   get_agent_diagnostics],
            middleware=[monitor_tool, log_before_model, report_prompt_switch],
        )

    def execute_stream(
        self,
        query: str,
        messages: list[dict[str, str]] | None = None,
        hidden_context: str | None = None,
    ):
        input_messages = list(messages or [])
        if hidden_context:
            input_messages.insert(0, {'role': 'system', 'content': hidden_context})
        input_messages.append({'role':'user','content':query})
        input_dict = {
            'messages': input_messages
        }
        # 第三个参数context就是上下文runtime中的信息,就是做提示词切换的标记
        for chunk in self.agent.stream(input_dict,stream_mode='values',context={'report':False}):
            latest_message = chunk['messages'][-1]
            if latest_message.content:
                yield latest_message.content.strip() + '\n'

if __name__ == '__main__':
    agent = ReactAgent()
    for chunk in agent.execute_stream('扫地机器人在我所在的地区的气温下如何保养'):
        print(chunk,end='',flush=True)
