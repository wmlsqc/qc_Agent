import time

import streamlit as st
from services import get_chat_service
from utils.config_handler import rag_conf
from utils.csv_handler import read_csv_rows

st.title('智扫通机器人智能客服')
st.divider()

if 'chat_service' not in st.session_state:
    st.session_state['chat_service'] = get_chat_service()

if 'messages' not in st.session_state:
    st.session_state['messages'] = []

if 'current_user_id' not in st.session_state:
    st.session_state['current_user_id'] = '1001'

if 'user_chat_histories' not in st.session_state:
    st.session_state['user_chat_histories'] = {}

if 'user_memories' not in st.session_state:
    st.session_state['user_memories'] = {}

if not st.session_state.get('messages_migrated_to_user_histories'):
    initial_user_id = st.session_state.get('current_user_id', '1001')
    st.session_state['user_chat_histories'].setdefault(
        initial_user_id,
        st.session_state.get('messages', []),
    )
    st.session_state['messages_migrated_to_user_histories'] = True

with st.sidebar:
    st.subheader('用户设置')
    user_rows = read_csv_rows('data/external/users.csv')
    user_options = [row.get('user_id', '') for row in user_rows if row.get('user_id')]
    if not user_options:
        user_options = ['1001']
    current_user_id = st.session_state.get('current_user_id', user_options[0])
    if current_user_id not in user_options:
        current_user_id = user_options[0]
    selected_user_id = st.selectbox(
        '当前用户ID',
        options=user_options,
        index=user_options.index(current_user_id),
    )
    st.session_state['current_user_id'] = selected_user_id
    st.session_state['messages'] = st.session_state['user_chat_histories'].setdefault(
        selected_user_id,
        [],
    )
    st.session_state['chat_service'].reset_context_debug_summary(
        selected_user_id,
        st.session_state['user_memories'].get(selected_user_id, {}),
        st.session_state['messages'],
    )
    st.divider()
    developer_debug_enabled = st.toggle('开发者调试模式', value=False)
    if developer_debug_enabled:
        st.subheader('开发者调试')
        st.caption(f"聊天模型：{rag_conf['chat_model_name']}")
        st.caption(f"Embedding模型：{rag_conf['embedding_model_name']}")
        context_summary = st.session_state['chat_service'].get_context_debug_summary()
        with st.expander('上下文摘要', expanded=False):
            st.caption(f"当前用户ID：{context_summary.get('user_id', '未设置')}")
            st.caption(
                "历史消息："
                f"{context_summary.get('history_message_count', 0)} / "
                f"{context_summary.get('history_limit', 10)}"
            )
            st.caption('存在记忆：' + ('是' if context_summary.get('has_memory') else '否'))
            st.caption(f"记忆字段数：{context_summary.get('memory_field_count', 0)}")
            st.caption(f"规划任务类型：{context_summary.get('planning_task_type', '未开始')}")
        st.divider()

    if st.button('清空会话', use_container_width=True):
        current_user_id = st.session_state.get('current_user_id', '1001')
        st.session_state['user_chat_histories'][current_user_id] = []
        st.session_state['messages'] = st.session_state['user_chat_histories'][current_user_id]
        st.session_state['chat_service'].reset_context_debug_summary(
            current_user_id,
            st.session_state['user_memories'].get(
                current_user_id,
                {},
            ),
            st.session_state['messages'],
        )
        st.rerun()

    st.subheader('快捷问题')
    quick_prompts = {
        '查询设备状态': '查询我的扫地机器人设备状态',
        '查询耗材状态': '查询我的扫地机器人耗材状态',
        '生成使用报告': '生成我的扫地机器人使用报告',
        '无法回充故障诊断': '我的扫地机器人最近无法回充，请帮我诊断',
    }
    for label, quick_prompt in quick_prompts.items():
        if st.button(label, use_container_width=True):
            st.session_state['pending_prompt'] = quick_prompt
            st.rerun()


def capture(generator, cache_list):
    try:
        for chunk in generator:
            cache_list.append(chunk)
            for char in chunk:
                time.sleep(0.01)
                yield char
    except Exception:
        fallback_message = '当前模型服务连接异常，请稍后重试。'
        cache_list.append(fallback_message)
        yield fallback_message


def handle_user_prompt(prompt: str):
    history = st.session_state['messages'][:]
    st.chat_message('user').write(prompt)
    st.session_state['messages'].append({'role': 'user','content': prompt})
    st.session_state['user_chat_histories'][
        st.session_state.get('current_user_id', '1001')
    ] = st.session_state['messages']

    response_messages = []
    with st.spinner('智能客服思考中...'):
        res_stream = st.session_state['chat_service'].stream_chat(
            prompt,
            user_id=st.session_state.get('current_user_id', '1001'),
            history=history,
            session_memory=st.session_state['user_memories'].setdefault(
                st.session_state.get('current_user_id', '1001'),
                {},
            ),
        )
        st.chat_message('ai').write_stream(capture(res_stream,response_messages))
        if response_messages:
            st.session_state['messages'].append({'role':'ai','content': ''.join(response_messages)})
            st.session_state['user_chat_histories'][
                st.session_state.get('current_user_id', '1001')
            ] = st.session_state['messages']

        st.rerun()


for message in st.session_state['messages']:
    st.chat_message(message['role']).write(message['content'])

pending_prompt = st.session_state.pop('pending_prompt', None)
if pending_prompt:
    handle_user_prompt(pending_prompt)

# 用户输入提示词
prompt = st.chat_input()

if prompt:
    handle_user_prompt(prompt)
