---
name: skill-curator
description: 根据多轮对话总结用户习惯、偏好和 SOP，并优化已有创作 skill 或创建新 skill
triggers:
  - 用户要求优化、更新、新建或细化 skill，让某类创作流程以后更稳定复用时。
  - 用户要求总结自己的习惯、偏好、固定 SOP 或多轮对话中反复出现的工作方式时。
  - 用户希望把一次成功的创作流程沉淀成可复用 Markdown skill 文件时。
allowed_tools:
  - create_sub_agent
  - read_file
  - write_file
  - edit_file
  - rename_file
  - list_files
  - grep_files
  - search_files
priority: 35
---
# Skill 策展

把稳定、可复用的创作偏好和工作流程沉淀为可执行的本地创作 skill。此 skill 同时服务主 Agent 的规则确认和子 Agent 的文件更新。

## 适用场景

- 用户要求新建、更新、优化、细化 skill。
- 用户要求总结习惯、沉淀 SOP、固定工作流或保存复用规则。
- 不适用于保存一次性需求、临时情绪、账号信息、API key 或私人身份信息。

## 角色边界

- 主 Agent：提炼可复用规则、说明目标文件和修改范围，必要时向用户确认；确认后调用 `create_sub_agent` 委派文件读取、改写和保存。
- 子 Agent：执行任务单，读取现有 skill，更新或创建 Markdown 文件；不能向用户提问或等待输入，信息不足时返回缺口和建议下一步。
- 主 Agent 不直接调用 `write_file`、`edit_file`、`rename_file` 修改 skill 文件。
- 子 Agent 修改 skill 时要保持触发信息准确，避免让主 Agent 误以为自己可以直接执行成品创作。

## 判断范围

只沉淀能复用的稳定偏好、写作标准、审稿标准、工作流程、命名习惯和主/子 Agent 分工规则。不要把一次性的闲聊、临时需求、情绪表达或单次项目细节写进 skill。

## 工作流程

1. 回顾当前多轮对话，提取可复用规则。
2. 使用 `list_files` 或 `search_files` 查看 `skills/` 下已有 skill。
3. 使用 `read_file` 读取可能需要更新的 skill；需要查内容时可用 `grep_files`。
4. 判断应该更新已有 skill，还是创建新 skill：
   - 已有 skill 的职责匹配时，优先更新。
   - 新规则属于独立流程或领域时，创建新 skill。
5. 先向用户说明准备沉淀的规则、目标文件、不会写入的内容。
6. 用户确认后，子 Agent 使用 `edit_file` 更新已有 skill，或使用 `write_file` 创建新 skill。
7. 需要重命名 skill 文件时，使用 `rename_file`，不要使用 `delete_file`。

## 写入规则

- 更新前先说明目标文件、准备加入的规则、不会写入的内容。
- 更新已有 skill 时保持 frontmatter 的 `name`、`description`、`triggers`、`allowed_tools`、`priority` 完整。
- 创建新 skill 时文件名使用小写短横线，正文优先写角色边界、流程、判断标准和输出要求。
- 新建或更新 skill 文件时只使用 `write_file` 或 `edit_file` 写 Markdown，文件扩展名必须是 `.md`。
- 需要废弃 skill 时建议重命名或让用户人工删除，不要使用 `delete_file`。
- 如果 skill 会触发具体创作、审稿、改写、整理成稿或文件修改，必须写清主 Agent 只委派、子 Agent 才执行。

## 输出要求

- 先给出提炼出的可复用规则。
- 再说明将更新哪个目标文件，以及为什么不是新建/为什么不是更新其他 skill。
- 修改后简述变更点，不要粘贴整篇 skill，除非用户要求。

## 写作标准

- skill frontmatter 必须包含 `name`、`description`、`triggers`、`allowed_tools`、`priority`。
- skill 文件必须是 Markdown，并使用固定格式：YAML frontmatter、一级标题、适用场景、角色边界、工作流程、输出要求、质量标准、常见误区。
- skill 正文要短而可执行，优先写流程、判断标准和输出要求。
- 不要在 skill 中保存敏感信息、API key、账号信息或私人身份信息。
- 不要使用 `delete_file`；需要废弃 skill 时，先建议重命名或让用户确认人工删除。

## 质量标准

- 规则必须可复用，可在未来相似任务中指导行为。
- 文案要短、明确、可执行，避免记录流水账。
- 工具权限要最小化，不给 skill 暴露不需要的工具。
- skill 必须符合当前 Agent 提示词：主 Agent 面向用户和委派，子 Agent 执行具体产出和文件修改。

## 常见误区

- 把一次性偏好写成长期规则。
- 把临时项目细节写进通用 skill。
- 未读取已有 skill 就重复创建。
- 未向用户说明目标文件就直接修改。
- 写出的 skill 仍要求主 Agent 直接生成正文、审稿或保存文件。
- 使用 `delete_file` 删除 skill。
