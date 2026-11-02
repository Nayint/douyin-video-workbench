# 第三方组件与发布边界

- React / FastAPI / Three.js / faster-whisper / BiliNote 等均保留各自上游许可；本项目 MIT 不替代这些许可。实际版本见依赖锁及参考环境清单。
- Dify 为外部服务，遵循 [Dify Open Source License](https://github.com/langgenius/dify/blob/1.17.1/LICENSE)。脚本只从固定版本官方下载源码，并在用户本机添加原有草稿保护，不将整个 Dify 重新声明为 MIT。
- `deploy/dify/workflows/` 为作者实际工作流的 `include_secret=False` 导出。需要导入者配置自己的模型供应商、API Key 和应用编号，不含私人数据库或样稿。
- `config/author-skills/pipi-copywriting/` 为工作台实际加载的提炼规则，保留来源署名；不含原始视频、逐字稿、语料索引或私人研究文件。引用的外部作者并非项目代言人。
- `frontend/public/duo/vendor/three/` 和 fflate 的许可随代码保留；详见 `frontend/public/duo/licenses/`。
- Apple 设备模型和纹理不随本仓库分发。它们不由本项目 MIT 授权，来源与校验值在 `frontend/public/duo/sources.json`。截图均使用独立虚构演示数据，不包含这些未分发模型。
- Ollama 权重、faster-whisper 权重需要单独下载并遵循相应模型卡许可，配置文件中的名称不是授权替代品。

`prepare_device_assets.py` 改编自 jadon7 的 MIT 资产准备脚本，保留归属及既有 fold-preview-MIT.txt；它只在使用者本机处理第三方模型，模型本身不包含在 Git 提交中。
