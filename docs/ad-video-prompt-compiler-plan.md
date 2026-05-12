# Jaaz 通用广告营销视频 Prompt Compiler 方案

## 1. 文档目的

本文档用于沉淀 Jaaz 在“分镜图生成 + 选中分镜图生成视频”场景下的完整优化方案。

目标不是做品牌资产管理系统，也不是为某一个品牌、某一个品类写死逻辑，而是：

- 将用户首轮输入中提供的品牌、产品、卖点、调性、平台等信息，编译成更专业的广告语言
- 提升分镜图和视频提示词的专业性、叙事性、镜头感和营销感
- 让整个流程从“模型直出”升级为“广告内容生成编译器”
- 先建立“通用广告专业性闭环”，后续如有需要再补“品牌资产闭环”

## 2. 当前背景与边界

### 2.1 当前系统现状

当前 Jaaz 已基本打通如下链路：

1. 用户输入广告需求
2. 生成分镜图
3. 在画布中选中分镜图
4. 生成视频
5. 视频回写到画布

但目前最核心的问题不在接口连通性，而在内容生成质量：

- 分镜图提示词过于粗糙
- 视频提示词过于粗糙
- 图像提示词和视频提示词没有明显分层
- “选中分镜图生成视频”这一关键环节没有专门的 prompt compiler
- 结果更像“AI 生成内容”，而不是“广告营销视频”

### 2.2 本阶段明确不做的事情

本阶段不优先做：

- 品牌资产系统
- 品牌 logo / 包装图 / KV / 设计规范管理
- 某个品牌或某个特定产品的专用知识库
- 强依赖资产注入的品牌一致性闭环

这些信息假设由用户在首轮 prompt 中注入，例如：

- 品牌名称
- 产品名称
- 产品卖点
- 风格调性
- 平台投放方向
- 受众与传播目的

### 2.3 本阶段明确要解决的问题

本阶段聚焦：

- 通用广告营销视频的专业性
- 从用户 prompt 到专业广告语言的编译
- 从分镜图到视频导演语言的编译
- 从生成结果到 QA / retry 的轻闭环

## 3. 核心判断

### 3.1 主要矛盾

当前主要矛盾不是“模型不够强”，而是：

用户输入通常是模糊的、口语化的，但输出要求却是接近专业广告制作语言的。

也就是说，系统面对的是：

- 模糊需求
- 专业输出

之间的结构性矛盾。

### 3.2 方案的本质

本方案的本质不是“把 prompt 写长一点”，而是增加一层编译：

用户自然语言
→ 广告创意意图
→ 分镜规划
→ 图像提示词
→ 视频提示词
→ QA / retry

因此，这个方案本质上是在把 Jaaz 从“模型调用器”升级成“广告内容 Prompt Compiler”。

## 4. 辩证分析

### 4.1 为什么方案成立

这个方案成立的原因在于：

- 它把“品牌 / 产品 / 卖点 / 调性”与“广告语法”分开
- 用户负责输入差异化信息
- 系统负责补齐专业广告语言
- 它把图像和视频两个不同任务分开建模
- 它让分镜图承担叙事和连续性职责，而不是仅仅生成几张好看的图

### 4.2 它解决了什么

它主要解决的是：

- 用户不会写专业广告 prompt
- 分镜图与视频脱节
- 视频缺少镜头节奏
- 内容像“AI 视觉片段”而不像“商业广告”
- 结果不可审稿、不可迭代、不可归因

### 4.3 它会引入什么新问题

任何结构化方案都有代价，本方案会引入：

- 生成链路更长
- token 成本增加
- 模型自由度下降
- 结果可能更稳定，但也可能更保守
- 如果没有 QA 和 retry，只会得到“结构化的普通结果”

### 4.4 结论

本方案值得做，但其定位必须清晰：

- 它不是“全自动广告终稿系统”
- 它是“广告生成编译器 + 专业表达增强层”
- 第一阶段的目标是显著提高下限和可控性
- 不是直接追求完全替代人的创意判断

## 5. 总体目标

在不做品牌资产闭环的前提下，本方案的目标是建立一个“通用广告专业性闭环”。

所谓“通用广告专业性闭环”，指的是：

1. 用户输入的品牌 / 产品 / 卖点 / 调性被结构化理解
2. 系统自动生成更专业的创意简报
3. 系统自动生成带叙事职责的分镜规划
4. 系统自动生成专业广告摄影级别的分镜图提示词
5. 系统将选中的分镜图编译成具有镜头、运动、节奏、收束逻辑的视频提示词
6. 系统对结果做广告完成度 QA
7. QA 不通过时进行重写或重试

## 6. 系统设计总览

建议将整个生成链路拆成 5 个层级。

### 6.1 Creative Brief Compiler

职责：

- 把用户输入转成专业广告创意简报

输出关注点：

- objective
- audience
- platform
- product_role
- single_minded_message
- tone
- mood
- visual_direction
- final_impression

### 6.2 Storyboard Compiler

职责：

- 把 brief 转成有叙事职责的分镜卡

每个分镜至少包含：

- shot_id
- narrative_role
- visual_goal
- subject
- scene
- camera
- lighting
- continuity_anchor
- motion_hint
- negative_constraints

### 6.3 Image Prompt Compiler

职责：

- 将每个分镜卡编译成更专业的图像提示词

重点关注：

- 商业构图
- 产品视觉中心
- 材质与布光
- 平台比例
- 画面层次
- 广告摄影感

### 6.4 Storyboard-to-Video Prompt Compiler

职责：

- 将“选中分镜图 + 原始 brief + 平台要求”编译成专业的视频导演提示词

重点关注：

- 起承转合
- 镜头运动
- 物理合理性
- 卖点 reveal
- 最终收束

### 6.5 Ad QA Layer

职责：

- 对生成结果做广告完成度检查

输出关注：

- 是否有开场钩子
- 是否有产品视觉中心
- 是否有卖点强化
- 是否有 hero packshot
- 是否适配平台投放
- 是否像“广告”而不是普通 cinematic clip

## 7. Creative Brief Compiler 设计

### 7.1 目标

这一步不是写给终端用户看的文案，而是内部结构化中间层。

### 7.2 建议 schema

```json
{
  "brand_or_product_context": "",
  "objective": "",
  "audience": "",
  "platform": "",
  "single_minded_message": "",
  "reason_to_believe": "",
  "tone": "",
  "mood_keywords": [],
  "visual_keywords": [],
  "product_priority": "",
  "cta_or_final_impression": "",
  "duration_seconds": 8,
  "aspect_ratio": "16:9"
}
```

### 7.3 编译原则

- 不重复抄用户原话
- 要做抽象和归纳
- 要把“好看、酷、高级”翻译成广告可执行目标
- 输出要服务于后续分镜和视频，而不是停留在文案层

## 8. Storyboard Compiler 设计

### 8.1 目标

分镜图不是截图，也不是插画拼图，而是视频的控制锚点。

### 8.2 推荐的通用广告叙事骨架

对于 8 秒视频，可先使用统一母版：

- Shot 1: Hook / 情绪或场景引入
- Shot 2: Product Reveal / 卖点强化
- Shot 3: Hero Resolution / 结尾收束

对于 6 秒视频：

- Shot 1: Hook + Product Entry
- Shot 2: Hero Packshot + Message Lock

### 8.3 分镜卡 schema

```json
{
  "shot_id": "S1",
  "narrative_role": "opening_hook",
  "visual_goal": "",
  "subject": "",
  "scene": "",
  "camera": "",
  "lighting": "",
  "composition": "",
  "continuity_anchor": [],
  "motion_hint": "",
  "negative_constraints": []
}
```

### 8.4 编译原则

- 每张图必须承担明确叙事职能
- 每张图都必须可单独审稿
- 不能只追求“都好看”
- 后续视频需要从中提取 continuity anchor

## 9. Image Prompt Compiler 设计

### 9.1 目标

图像提示词的目标不是普通出图，而是产出“可作为广告分镜图审稿”的 still。

### 9.2 推荐结构

每张分镜图提示词建议由 5 部分组成：

1. Creative Intent
2. Shot Design
3. Subject and Product
4. Scene and Lighting
5. Negative Constraints

### 9.3 推荐模板

```text
[Creative Intent]
Create a premium storyboard keyframe for a commercial campaign.
This frame should communicate {single_minded_message} with a {tone} feeling.
This is {shot_id}, serving as {narrative_role}.

[Shot Design]
{shot_type}, {camera_angle}, {lens_feel}, {composition}, clear focal hierarchy.
The product must remain the visual hero.
Frame the image for {aspect_ratio}.

[Subject and Product]
Show {product_description} with clear form, material, silhouette, and visual priority.
If human talent appears, performance should feel premium, controlled, and commercially believable.

[Scene and Lighting]
Set in {scene_description}. Lighting is {lighting_setup}.
Use controlled commercial reflections, strong material readability, and premium surface rendering.
Mood: {mood_keywords}.

[Continuity Anchors]
Maintain consistency with prior and subsequent storyboard frames: {continuity_anchor}.

[Negative Constraints]
No clutter, no cheap CGI feel, no distorted packaging, no random objects, no awkward anatomy, no off-tone styling, no visual confusion.
```

### 9.4 图像层的专业增强重点

系统要自动补充的不是品牌词，而是通用广告摄影语言，例如：

- hero product framing
- commercial focal hierarchy
- controlled reflections
- restrained palette
- negative space discipline
- material clarity
- premium lighting
- platform-friendly composition

## 10. 选中分镜图生成视频的专用设计

### 10.1 为什么这是单独的一层

“选中分镜图生成视频”不是普通文生视频。

它本质上是：

- 静态参考图
→ 时间连续的广告镜头

这里的关键矛盾是：

- 图片告诉模型“长什么样”
- 视频需要模型知道“怎么动、为什么这样动、最后怎么收”

因此必须有专门的 Storyboard-to-Video Prompt Compiler。

### 10.2 输入

- 用户原始 prompt
- Creative Brief
- 被选中的分镜图
- duration / aspect ratio / resolution

### 10.3 输出的核心问题

要明确：

- 从哪一张图开始
- 最终落到哪一张图
- 镜头怎么过渡
- 哪些元素可以动
- 哪些元素必须稳定
- 如何完成卖点递进
- 如何形成商业广告式收束

### 10.4 推荐 Video Brief schema

```json
{
  "opening_frame_role": "",
  "ending_frame_role": "",
  "transition_style": "",
  "camera_motion_rules": [],
  "product_motion_rules": [],
  "environment_motion_rules": [],
  "brand_lock_rules": [],
  "final_packshot_rules": [],
  "negative_rules": []
}
```

### 10.5 推荐视频提示词模板

```text
Create an {duration}-second premium commercial film in {aspect_ratio}, {resolution}.

Objective:
{objective}

Audience feeling:
{audience_feeling}

Single-minded message:
{single_minded_message}

Use the attached storyboard images as continuity anchors for composition, product shape, color direction, and campaign mood.

Narrative structure:
- Opening: begin with the visual language and emotional hook of reference image 1
- Development: reveal the product and strengthen the key selling impression through controlled cinematic movement
- Resolution: end in the hero composition and commercial clarity of reference image 2

Camera language:
{camera_language}

Motion language:
{motion_language}

Lighting and atmosphere:
{lighting_rules}

Commercial rules:
- Keep the product recognizable at all times
- Maintain clean focal hierarchy
- Avoid chaotic motion
- End on a strong hero packshot suitable for marketing usage

Negative rules:
- No rubbery motion
- No random objects
- No identity drift
- No awkward morphing
- No messy ending
- No cinematic filler without product value
```

### 10.6 专业增强重点

系统需要补充的广告级视频语言包括：

- premium commercial pacing
- intentional reveal
- camera-led product emphasis
- clean final brand resolution
- realistic material and motion physics
- packshot-ready ending

## 11. 通用广告专业性 QA 设计

### 11.1 目标

QA 的目标不是检查“模型有没有返回结果”，而是检查“结果是不是像广告”。

### 11.2 推荐 QA rubric

建议至少包含以下维度：

```json
{
  "opening_hook_strength": 0,
  "product_visibility": 0,
  "selling_point_clarity": 0,
  "commercial_composition_quality": 0,
  "motion_quality": 0,
  "final_packshot_strength": 0,
  "platform_readiness": 0,
  "overall_ad_feel": 0
}
```

### 11.3 QA 关键问题

应检查：

- 是否有明确开场钩子
- 产品是否始终清晰
- 卖点是否被强化
- 视频是否像广告而不是普通 cinematic clip
- 是否有清晰的收束
- 最后一帧是否可作为 key visual 或 hero frame

## 12. Retry / Rewrite 策略

### 12.1 为什么必须有 retry

没有 retry，就不是闭环，只是一次性生成流程。

### 12.2 推荐失败归因维度

若 QA 不通过，应归因为：

- 分镜图本身不合适
- 选图策略不对
- 视频 prompt 太散
- 镜头语法不够明确
- 结尾收束不够强
- 动作元素过多，产品被冲淡

### 12.3 推荐修复动作

- 重写 video prompt
- 调整 opening / ending frame 选择
- 减少中间运动复杂度
- 强化 final packshot 约束
- 强化 product lock / focal hierarchy 约束

## 13. 闭环判断

### 13.1 本方案能形成什么闭环

在不做品牌资产闭环的前提下，本方案可以形成：

通用广告专业性闭环。

即：

用户输入
→ brief compiler
→ storyboard compiler
→ image prompt compiler
→ selected storyboard to video compiler
→ ad qa
→ retry / rewrite

### 13.2 本方案不能保证什么

本方案不能保证：

- 强品牌资产一致性
- 所有视频都能成为终稿
- 完全替代人工创意判断
- 所有品类都自动达到顶级广告质感

它的更现实定位是：

- 显著提高下限
- 提高可控性
- 提高“像广告”的概率
- 为后续人工筛选和修正提供高质量底稿

## 14. 落地优先级

### P0：必须做

1. Creative Brief Compiler
2. Storyboard Compiler
3. Image Prompt Compiler
4. Storyboard-to-Video Prompt Compiler
5. 通用广告 QA rubric

### P1：强烈建议做

1. Retry / rewrite rules
2. 选中分镜图时的 opening / ending frame 角色推断
3. 结尾 hero packshot 强约束

### P2：后续增强

1. 品牌资产层
2. 平台定制模板
3. 品类专用广告模板
4. 更细粒度的 shot grammar

## 15. 与当前代码的对应关系

当前最相关的代码路径包括：

- [server/services/langgraph_service/configs/image_vide_creator_config.py](../server/services/langgraph_service/configs/image_vide_creator_config.py)
- [server/services/direct_video_service.py](../server/services/direct_video_service.py)
- [react/src/components/chat/ChatCanvasVideoGenerator.tsx](../react/src/components/chat/ChatCanvasVideoGenerator.tsx)

后续实现时，建议将 prompt compiler 逻辑放在服务端，而不是前端。

原因：

- 更便于统一策略
- 更便于 QA 和 retry
- 更便于后续扩展品牌资产层

## 16. 推荐的实现路径

### 第一阶段

做最小可用版本：

- Brief schema
- Storyboard schema
- 视频 prompt 模板
- QA rubric

### 第二阶段

让系统真正参与生成控制：

- 分镜 prompt 自动编译
- 选中分镜图时自动生成 video brief
- 自动把 prompt 送到 direct video generation

### 第三阶段

加入闭环能力：

- QA 后自动 rewrite
- retry 策略
- 多轮 prompt 优化

## 17. 总结

本方案的核心不是“提示词写得更华丽”，而是：

让 Jaaz 具备一套通用广告营销内容的专业编译能力。

用户提供：

- 品牌
- 产品
- 卖点
- 调性
- 平台目标

系统负责：

- 专业广告语言编译
- 分镜叙事编译
- 商业摄影语言编译
- 视频导演语言编译
- 结果 QA 与重试

这是当前阶段最合理、最聚焦、也最有产品价值的方向。
