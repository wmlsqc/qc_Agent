# 记忆模块说明

`memory/` 目录提供当前项目的轻量本地记忆能力。它用于保存非敏感的用户业务偏好，帮助 Agent 在当前项目范围内做更个性化的设备、耗材、清扫和故障建议。

## 主要文件

- `local_memory.py`：本地 JSON 记忆读写、合并、提取和格式化逻辑。
- `user_memory.json`：运行时生成的用户记忆文件，已在 `.gitignore` 中忽略，不应提交到仓库。

## 存储位置

```text
memory/user_memory.json
```

## 允许保存的字段

当前允许保存以下非敏感业务字段：

- `user_id`
- `house_area_sqm`
- `family_size`
- `floor_type`
- `has_pet`
- `has_carpet`
- `common_faults`
- `cleaning_goal`
- `cleaning_preference`
- `preferred_cleaning_time`
- `frequent_cleaning_areas`
- `updated_at`

## 不应保存的信息

本模块不应保存以下内容：

- API Key
- 密码
- 账号凭据
- 电话
- 地址
- 用户完整原始聊天隐私内容
- 其他敏感个人信息

## 当前工作方式

记忆来源包括：

- `data/external/users.csv` 中的用户画像。
- 用户当前消息中表达的非敏感偏好，例如房屋面积、是否有宠物、是否有地毯、常见故障和清扫偏好。
- Streamlit 当前会话中的临时记忆。

记忆合并时，当前会话记忆优先于本地 JSON 记忆。读取或写入失败时会自动降级，不影响正常对话。

## 当前限制

本模块适合演示和轻量二次开发，不适合直接作为生产环境多人并发记忆系统。后续可以升级为数据库、缓存服务或具备权限控制的用户画像服务。
