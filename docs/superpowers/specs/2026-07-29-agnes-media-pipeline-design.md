# Agnes 媒体生成管线设计

**日期：** 2026-07-29  
**状态：** 已确认  
**范围：** ZeroRealm 官网主页与微信公众号每日发布

## 1. 目标

建立一套由 `zerorealm-data` 统一管理的 Agnes 媒体生成能力：

- 官网主页生成一组固定使用的品牌配图和展示视频，只有执行手动命令时才重新生成。
- 每篇公众号日报在发布前自动生成 1 张封面图、3 张正文配图和 1 条约 15 秒、9:16 的短视频。
- 短视频同时进入公众号文章和本地素材库，供视频号或其他平台复用。
- Agnes 生成失败、下载失败或素材校验失败时，阻止自动发布，保留失败记录并输出明确错误。
- Agnes API Key 只从 `AGNES_API_KEY` 环境变量读取，不进入仓库、日志或前端代码。

## 2. 已有系统约束

- `zerorealm-data` 已有 `PublishWorkflow`、可插拔 Pipeline Step、`MediaReference`、`AssetManager` 和微信公众号 Publisher。
- 当前公众号流程只有本地封面上传；正文媒体处理函数仍为空。
- 当前官网主页没有图片或视频资源字段。
- 官网设计规范禁止视频背景和自动播放，因此新增视频使用显式播放控件，配图使用 `next/image`，不引入轮播或动画库。
- 两个 Git 仓库当前都有既有工作；实现不得覆盖或提交无关改动。

## 3. 方案

采用“统一媒体生成层”：

```text
AgnesMediaClient
       |
       v
MediaGenerationService ---- PromptBuilder
       |
       +---- HomepageMediaCommand
       |          |
       |          +---- zerorealm-website/public/media/home/*
       |          +---- homepage-media.json
       |
       +---- GenerateMediaStep
                  |
                  +---- assets/generated/YYYY-MM-DD/*
                  +---- media-manifest.json
                  |
                  v
          WechatRenderer / WechatPublisher
```

官网与公众号共享认证、请求、重试、异步轮询、下载、哈希和清单逻辑；消费者只负责各自的提示词输入、布局和渠道上传。

## 4. Agnes 接口适配

### 4.1 默认配置

- Base URL：`https://apihub.agnes-ai.com/v1`
- 图片模型：`agnes-image-2.1-flash`
- 视频模型：`agnes-video-v2.0`
- 图片端点：`POST /images/generations`
- 视频创建端点：`POST /videos`
- API Key：`AGNES_API_KEY`

所有端点和模型都可由环境变量覆盖，以兼容 Agnes 后续接口调整：

- `AGNES_BASE_URL`
- `AGNES_IMAGE_MODEL`
- `AGNES_VIDEO_MODEL`
- `AGNES_VIDEO_CREATE_PATH`
- `AGNES_VIDEO_STATUS_URL_TEMPLATE`

### 4.2 图片响应

客户端兼容以下返回形式：

- `data[0].url`
- `data[0].b64_json`
- Data URI

远程 URL 必须下载到本地，发布流程不依赖临时 Agnes URL。

### 4.3 视频异步任务

创建请求后，从 `video_id`、`id` 或 `task_id` 中提取任务标识。轮询地址由
`AGNES_VIDEO_STATUS_URL_TEMPLATE` 生成，默认使用 Agnes 当前的 `video_id` 查询方式。
轮询采用有上限的退避策略，不无限等待。

成功响应从常见的 `url`、`video_url`、嵌套 `data` 或输出列表中提取视频 URL。
`failed`、`cancelled`、超时、响应结构未知都属于阻断性错误。

## 5. 媒体规格

### 5.1 官网主页

- Hero 主视觉图：16:9，桌面与移动端使用响应式裁切。
- 展示视频：16:9，静音默认关闭，不自动播放，带原生控制条和 poster。
- 风格：高可信、克制、科技感，遵循 ZeroRealm Navy / Blue / Emerald 品牌色。
- 生成后固定保存到 `zerorealm-website/public/media/home/`。
- `homepage-media.json` 记录文件路径、尺寸、MIME、SHA-256、生成时间、模型和提示词版本。
- 手动命令默认拒绝覆盖已有素材；显式传入 `--force` 才重新生成。

### 5.2 公众号日报

- 封面图：900×383。
- 正文图：3 张，默认 1280×720，分别服务于开篇、核心分析和决策/趋势段落。
- 短视频：约 15 秒，720×1280，9:16。
- 素材目录：`assets/generated/<date>/`。
- 清单：`assets/generated/<date>/media-manifest.json`。
- 同一文章 UUID、内容修订号和提示词版本命中有效清单时复用素材，避免重试发布时重复计费。

## 6. 公众号数据流

Pipeline 顺序调整为：

```text
Parse
  -> ValidateStep
  -> GenerateMediaStep
  -> ValidateMediaStep
  -> RenderStep
  -> PublishStep
  -> RecordStep
```

`GenerateMediaStep` 只在微信目标、非 preview 且启用 `media.enabled` 时调用 Agnes。
它把生成的媒体集合写入 `PipelineState.MEDIA_BUNDLE`，并把封面路径同步到 Article。

`ValidateMediaStep` 验证：

- 文件存在且非空。
- MIME 与扩展名一致。
- 图片可解码且尺寸满足要求。
- 视频可被探测，尺寸比例与时长在允许范围内。
- 清单中文件 SHA-256 与实际文件一致。

`WechatRenderer` 从 `MEDIA_BUNDLE` 取得 3 张图片，在三个固定语义位置插入图片块。
`WechatPublisher` 先把正文图片上传到微信 CDN，再替换 HTML 中的本地占位符；封面继续使用永久图片素材接口。

视频先上传为微信永久视频素材并保存 `media_id`。文章内嵌使用独立的
`WechatVideoEmbedder`，避免将微信特有标记散落到通用 Renderer。若账号权限、视频上传或内嵌标记校验失败，发布按既定策略阻断；本地视频文件和失败清单仍保留，供排查和后续视频号复用。

## 7. 官网数据流

新增手动命令：

```text
python generate_media.py homepage [--force]
```

命令读取品牌规范和固定提示词，生成 Hero 图片、视频 poster 和展示视频，写入官网静态目录及清单。

官网新增 `HomeMedia` 组件：

- 使用 `next/image` 展示 Hero 配图。
- 使用原生 `<video controls preload="metadata">` 展示视频。
- 不自动播放、不循环、不作页面背景。
- 提供 poster、可访问名称和不支持视频时的文本回退。
- 资源来自静态清单，不在浏览器或 Next.js Server Component 中直接调用 Agnes。

## 8. 配置

`config/publish.yaml` 新增：

```yaml
media:
  enabled: true
  provider: agnes
  image_model: agnes-image-2.1-flash
  video_model: agnes-video-v2.0
  body_image_count: 3
  video_duration_seconds: 15
  video_aspect_ratio: "9:16"
  poll_interval_seconds: 5
  poll_timeout_seconds: 600
  reuse_existing: true
```

配置模型保存非敏感默认值；密钥和可选端点覆盖只来自环境变量。

## 9. 错误处理与可恢复性

- 401/403：不重试，提示密钥无效或无权限。
- 408/429/5xx 和网络超时：按现有 Pipeline 退避策略有限重试。
- 内容策略拒绝：不重试，记录不含密钥的错误摘要。
- 视频轮询超时：标记生成失败，阻断发布。
- 下载失败、零字节文件、MIME 或尺寸错误：标记校验失败，阻断发布。
- 任一每日素材失败时不使用默认素材、不使用前一天素材、不创建或提交公众号草稿。
- 成功下载的部分素材保留；下一次运行根据清单只补齐缺失项。
- 日志不得打印 Authorization 请求头、API Key 或完整 Base64 响应。

## 10. 测试策略

### 10.1 Agnes 客户端

- Bearer 认证、模型和尺寸请求正确。
- URL、Base64 和 Data URI 图片响应都可处理。
- 视频任务 ID 的兼容提取与状态轮询。
- 401 不重试；429/5xx 可重试；超时终止。
- 日志与异常消息不泄露密钥。

### 10.2 生成服务

- 生成 1+3+1 的完整媒体集合。
- 已有有效清单时复用。
- 内容修订号或提示词版本改变时重新生成。
- 部分成功后再次运行只补齐缺失项。
- 原子写入清单，避免中断留下“已完成”的假状态。

### 10.3 Pipeline

- `GenerateMediaStep` 位于 Validate 与 Render 之间。
- Agnes 失败时 Render、Publish、Record 不执行。
- preview 模式不调用 Agnes。
- 素材校验失败时发布被阻断。

### 10.4 微信

- 正文图片上传后本地占位符全部替换为微信 CDN URL。
- 封面使用生成封面。
- 视频上传和内嵌适配器收到正确素材标识。
- 视频权限或上传失败时不创建草稿。

### 10.5 官网

- 清单解析正确。
- Hero 图片具有确定尺寸与 alt。
- 视频有 controls、poster，且没有 autoplay。
- 缺失清单时组件提供可读回退，不导致构建失败。
- `npm test`、`npm run lint`、`npm run build` 全部通过。

## 11. 发布与运维

- 实现阶段不使用聊天中已经暴露的旧 Key。
- 在部署环境中设置重新生成的 `AGNES_API_KEY`。
- 首次上线先以 dry-run 生成并校验每日素材，不提交微信草稿。
- 微信图片与视频上传通过测试账号或受控草稿验证后再启用正式自动发布。
- 官网素材只在手动命令成功且通过构建检查后更新。

## 12. 完成标准

- 官网主页可展示 Agnes 生成的固定配图和手动播放视频。
- 手动命令可在不覆盖已有素材的前提下生成或显式重新生成官网素材。
- 每日公众号发布前自动产出并校验 1 张封面图、3 张正文图和 1 条短视频。
- 正文图片可进入微信正文，短视频同时进入文章内嵌流程和可复用素材库。
- Agnes 或媒体校验失败时不会创建或发布公众号草稿。
- 所有新增逻辑有自动化测试，两个仓库原有测试、lint 和构建保持通过。
