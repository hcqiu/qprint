# 理想的用户环境配置流程
用户首次安装
    ↓
确保 conda 可用 (在Anaconda Prompt / Miniconda Prompt运行 conda init powershell)
    ↓
conda env create -p .\.conda -f environment.yml

以后 Agent
    ↓
不执行 conda activate
    ↓
conda run -p .\.conda python ...

# knowledge navigator agent

规范要求用户在Qprint文件夹启动Hermes agent/opencode/ deepseek Harness等，或者在chatgpt/codex/Claude code中打开Qprint文件夹。
Qprint UI
   │
   │ 用户点击 node A
   ▼
Qprint runtime （实时更新）
   │
   ├── workspace = foo
   ├── current_node = node-A
   ├── current_document = xxx.tex
   ├── selection = ...
   └── session = ...
           ▲
           │
    qprint agent state
           ▲
           │
  Codex / Claude / Hermes / OpenCode
于是 Agent 不需要猜：
用户说的“这里”到底是哪？

它直接读取：
qprint agent state

agent能接触到的一切skill里写的、tool返回的，都是相对路径。