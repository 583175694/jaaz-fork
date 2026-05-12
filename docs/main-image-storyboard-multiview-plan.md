# Jaaz 主图驱动分镜与多机位多视角综合方案

## 1. 文档目的

本文档用于统一沉淀 Jaaz 在以下方向上的综合方案：

- 主图 / 首帧 → 分镜
- 多机位 / 多视角分镜
- 角色与主体一致性控制
- 分镜生成前与视频生成前的 prompt 确认
- 中文展示、英文执行的双语 prompt 机制
- 右侧对话框与单图弹框的双轨交互
- 技术框架、对象模型、MVP 范围与任务拆分

这是一份合并后的主文档。它替代此前拆开的 PRD、技术设计、UX 状态、实现准备和 MVP 任务清单，作为后续讨论与落地的单一基线文档。

## 2. 背景与问题

当前 Jaaz 已基本打通：

1. 用户输入需求
2. 生成图片或分镜图
3. 在画布中选中分镜图
4. 继续生成视频
5. 将结果回写画布

但如果要进一步提升“主图扩展成分镜”和“分镜支持多视角”的能力，仅靠现有的单次 prompt 生成已经不够。当前主要问题是：

- 用户输入一句话，系统直接生成若干图
- 图像之间缺少明确的镜头职责
- 不同图之间缺少连续性约束
- 多视角更多停留在 prompt 文本，而不是用户可操作的镜头语言
- 单图精修和整组分镜之间缺少统一的交互系统
- 分镜生成前与视频生成前缺少标准化 prompt 审阅环节
- prompt 既服务于用户理解，又服务于模型执行，目前未清晰分层

如果继续沿用这种范式，系统更容易产出“彼此相似但缺少镜头组织”的图组，而不是“为视频服务的分镜系统”。

## 3. 核心判断

### 3.1 本次方案的本质

本次方案的本质不是：

- 增加几个角度预设
- 把 prompt 写得更长
- 引入一个新的外部平台

而是把 Jaaz 的生成链路从：

用户输入
→ 直接生成图片

升级为：

用户输入 / 主图
→ 主图解析
→ 分镜规划
→ 多视角展开
→ 连续性控制
→ 用户筛选
→ 再进入视频

也就是说，Jaaz 需要从“图像生成器”进一步升级为“分镜与镜头组织系统”。

### 3.2 借鉴 LibTV 的正确方式

本方案参考 LibTV 的核心，不在于复刻某个平台或接入新的外部服务，而在于吸收其方法论：

- 用主图 / 首帧驱动后续分镜扩展
- 每个分镜不是唯一图，而是一组多机位候选
- 用连续性约束保证人物、产品、场景和风格不漂移
- 用导演式交互取代纯 prompt 式交互

因此，借鉴 LibTV 的重点不是“像不像它的 UI”，而是：

- 是否建立了分镜中间层
- 是否建立了镜头语义层
- 是否建立了连续性控制层

## 4. 辩证分析

### 4.1 为什么这个方向值得做

这个方向成立，是因为它同时解决了内容组织和用户交互两个问题。

在内容组织层面：

- 主图不再只是参考图，而是整个分镜系统的视觉母版
- 分镜不再是若干散图，而是有叙事职责的镜头序列
- 多视角不再只是结果随机性，而是同一镜头的表达候选

在用户交互层面：

- 用户不再只能用自然语言猜模型
- 用户可以像导演一样选择镜头和机位
- 用户可以在整组分镜与单镜头精修之间切换

### 4.2 它真正解决了什么

本方案主要解决以下问题：

- 如何把一张主图扩展成一组可用于视频的分镜
- 如何让分镜中的每张图承担不同职责，而不是重复出图
- 如何让同一个分镜拥有多个机位 / 视角候选
- 如何在多轮生成中保持人物、产品、服装、场景和风格稳定
- 如何让用户通过更直观的镜头语言，而不是抽象 prompt，去微调单图结果
- 如何在高成本生成前让用户确认 prompt
- 如何把“中文可读性”和“英文可执行性”统一起来

### 4.3 它会引入什么新问题

这个方案虽然有价值，但必须正视它引入的新复杂度：

- 生成链路更长
- 成本和等待时间增加
- 模型自由度被连续性约束压缩
- 多视角 UI 容易过度承诺“像真实 3D 相机一样精确”
- 如果模型对视角变化和一致性的兑现能力不足，用户会感受到 UI 很强但结果不稳
- 文档、对象和状态如果不统一，很容易演变成复杂但脆弱的系统

### 4.4 结论

这个方向值得做，但定位必须清晰：

- 它不是一个真实三维相机系统
- 它是一个“镜头语义控制器 + 连续性增强器”
- 它最适合作为分镜工作流的中间层
- 它应优先承诺“更稳定的多视角候选生成”，而不是“精确 3D 旋转”

## 5. 产品目标

本功能的目标不是单纯增加一个“换角度”按钮，而是建立一套新的分镜工作流：

- 用户可以从主图 / 首帧出发生成结构化分镜
- 每个分镜可以生成多个机位 / 视角候选
- 用户可以对单张图进行导演式镜头微调
- 用户在分镜生成前和视频生成前都能确认 prompt
- 用户看到的是中文可读 prompt，模型接收的是英文执行 prompt

最终目标是让用户感觉自己在“组织镜头”和“导演画面”，而不是在反复猜 prompt。

## 6. 核心用户与典型场景

### 6.1 核心用户

- 广告创意用户
- 短视频内容创作者
- 角色设定和镜头分镜用户
- 需要从单图扩展到视频的用户

### 6.2 典型场景

#### 场景 A：主图生成分镜

用户已有一张人物或产品主图，希望基于它扩展出一组线性分镜，用于后续视频生成。

#### 场景 B：主图生成平行素材

用户已有一张主图，希望生成同一主体的多组不同机位、不同姿态、不同景别的素材。

#### 场景 C：单图机位精修

用户已经生成了一张较满意的图，但希望把这张图改成更低机位、更侧面、更近或更远的镜头表达。

#### 场景 D：分镜生成视频前确认

用户已拿到一组分镜候选，希望在系统生成视频前，先确认视频 prompt 是否符合预期。

## 7. 产品原则

### 7.1 分镜优先

系统优先帮助用户建立镜头结构，而不是直接输出更多图片。

### 7.2 候选优先

系统优先输出多个有组织的镜头候选，而不是强行给出唯一答案。

### 7.3 连续性优先

当用户从主图扩展分镜，或对单图进行机位编辑时，系统默认优先保持人物、产品、服装、场景和风格的一致性。

### 7.4 中文可理解，英文可执行

系统对用户展示中文 prompt，对模型执行英文 prompt，但两者必须语义对齐。

### 7.5 生成前可确认

系统生成分镜前和生成视频前，都必须允许用户确认即将提交给模型的 prompt。

## 8. 总体框架

建议将整个系统拆成 5 层：

### 8.1 意图理解层

输入：

- 用户中文需求
- 主图 / 首帧
- 可选的比例、风格、用途、输出规模

职责：

- 理解用户要做的是广告、剧情、展示片还是角色设定
- 判断主图是人物、产品、场景还是复合主体
- 判断更适合做线性分镜还是平行素材扩展

### 8.2 主图解析层

职责：

- 识别主图中的主体是谁
- 识别角色、产品、场景、风格、灯光等关键锚点
- 提炼后续所有分镜都应优先继承的信息

主图在本方案中不只是参考图，而是同时承担三种角色：

- 视觉母版
- 连续性锚点
- 分镜起点

### 8.3 分镜规划层

职责：

- 先决定“讲什么”，再决定“怎么拍”
- 把主图扩成一组有镜头职责的 shot
- 每个 shot 都描述自身在整段内容中的作用

典型 shot 可以包括：

- 开场建立
- 动作推进
- 卖点强化
- 情绪收束
- Hero 结束

### 8.4 多视角展开层

职责：

- 为每个 shot 生成多个机位 / 视角候选
- 让用户看到“同一镜头不同拍法”，而不是更多随机图

核心原则：

- 一个 shot 对应一个叙事职责
- 一个 shot 可以拥有多个 variant
- variant 的差异主要体现在机位、视角、景别和构图重心上

### 8.5 连续性控制层

职责：

- 让所有 shot 和 variant 都属于同一个世界和同一个主体系统

连续性控制的对象不应局限于“角色长得像”，而应该覆盖：

- 人物身份
- 服装和造型
- 产品形态和材质
- 场景属性
- 光线逻辑
- 风格语气

## 9. 核心抽象

### 9.1 Main Image Anchor

指主图所沉淀出来的视觉锚点集合。它回答的是：

- 后续镜头要围绕谁展开
- 哪些信息必须被保留
- 允许哪些维度发生变化

### 9.2 Shot

Shot 是分镜中的最小叙事单元。它回答的是：

- 这一镜头承担什么叙事职责
- 它和前后镜头的关系是什么
- 它应优先继承哪些连续性信息

### 9.3 Variant

Variant 是同一个 shot 的不同拍法候选。它回答的是：

- 同一个镜头可以如何拍
- 这一拍法更强调人物、产品还是环境
- 更适合做开场、推进、转场还是收束

### 9.4 Continuity Bible

Continuity Bible 是统一的连续性规则集。建议把连续性分为两类：

- 硬约束：人物脸、服装主形、产品结构、包装、品牌特征
- 软约束：光线、氛围、构图语气、景深、节奏感、情绪温度

### 9.5 Prompt Bundle

Prompt Bundle 是面向任务级别的 prompt 容器，建议同时承载：

- display_prompt_zh
- execution_prompt_en
- task_type
- display_summary
- source_context
- confirmation_required

它解决的是：

- 用户看什么
- 模型执行什么
- 这两者如何从同一个中间语义层生长出来

## 10. 主图 / 首帧 → 分镜方案

### 10.1 目标

让用户可以从一张主图或首帧出发，生成一组连贯分镜，而不是若干无组织的扩散图。

### 10.2 推荐模式

建议优先支持两种模式：

#### 模式 A：线性分镜扩展

适用于：

- 后续要继续做视频
- 需要明确的开场、推进、收束关系
- 希望分镜之间具备连续叙事性

典型结构：

- Shot 1：建立人物 / 场景
- Shot 2：推进动作 / 视线 / 状态
- Shot 3：强化卖点 / 冲突 / 关系
- Shot 4：收束 / Hero 结果

#### 模式 B：平行素材扩展

适用于：

- 更偏广告素材、角色设定、商品图组
- 需要同主题下的不同场景和姿态

### 10.3 当前阶段建议

优先做模式 A，即：

主图
→ 线性分镜
→ 再桥接视频

因为这条链路和 Jaaz 当前“选中分镜图生成视频”的路径更一致，也更容易形成系统闭环。

## 11. 多机位 / 多视角分镜方案

### 11.1 目标

让“多视角”不只是文本描述，而是一个用户可操作、系统可理解、模型可复用的镜头控制层。

### 11.2 基本原则

- 多视角不是更多随机图
- 多视角是同一个 shot 的不同镜头表达
- 用户调的是机位语义，不是 prompt 文本
- 系统输出的是候选，而不是唯一答案

### 11.3 交互定位

建议把这套能力定位为：

- 单图镜头编辑器
- shot 级别的 variant 生成器
- 面向高级用户的导演式精修能力

不建议把它定位为：

- 真实三维相机
- 全局默认主入口
- 对所有图像都有效的精确控制系统

### 11.4 核心交互控件

建议采用如下交互逻辑：

- 一个 3D 球体 / 球面隐喻控件
- 主体位于中心
- 球面上的摄像机表示当前机位
- 水平拖动表示围绕主体环绕
- 垂直俯仰通过一组滑杆或小拖拉条调节
- 景别缩放通过滑杆调节
- 通过预设视角快速切入典型拍法

其本质不是 3D 建模编辑，而是一个“伪 3D 摄像机语义控制器”。

### 11.5 推荐参数轴

建议优先向用户暴露 3 个主参数：

- 水平环绕
- 垂直俯仰
- 景别缩放

在此基础上，再通过预设视角承载典型组合：

- 左前 45°
- 右前 45°
- 侧面
- 背面
- 轻微俯拍
- 明显俯拍
- 轻微仰拍
- 明显仰拍
- 全身
- 中景
- 近景

## 12. 角色与主体一致性控制

### 12.1 一致性不只是“脸像”

一致性控制不能只理解为角色脸部一致，还应覆盖：

- 人物身份一致
- 服装和发型一致
- 产品形状和材质一致
- 构图气质和风格一致
- 场景逻辑和光线逻辑一致

### 12.2 两类规则

#### 硬一致性

这些内容优先不变：

- 人物身份
- 面部结构
- 发型
- 主服装
- 产品轮廓
- 产品包装
- 关键品牌视觉特征

#### 软一致性

这些内容可以有控制地变化：

- 姿态
- 机位
- 景别
- 场景轻微变化
- 背景层次
- 情绪和镜头语气

### 12.3 为什么必须默认继承一致性

用户在进行主图扩展或单图机位编辑时，天然预期是：

- 还是同一个人
- 还是同一件产品
- 还是同一套视觉世界

如果每次改角度都像重新创作，那这套能力就不是“机位编辑”，而是另一个随机生成入口。

## 13. 信息架构与交互模式

整体采用双轨结构：

- 右侧对话框：负责整组生成与自然语言表达
- 单图弹框：负责单镜头导演式调整

### 13.1 右侧对话框

职责：

- 输入需求
- 上传或引用主图
- 触发主图生成分镜
- 触发批量分镜生成
- 触发视频生成
- 承载 prompt 确认
- 输出生成结果摘要

### 13.2 画布结果区

职责：

- 承载主图
- 承载分镜结果
- 组织 shot 与 variant
- 允许选中单图进入镜头编辑弹框
- 允许从结果中选择分镜继续生成视频

### 13.3 单图镜头编辑弹框

职责：

- 调整水平环绕
- 调整俯视 / 仰视
- 调整景别缩放
- 选择预设视角
- 对单图重新生成候选
- 将结果替换当前图或加入候选组

## 14. 端到端用户流程

### 步骤 1：选择主图

用户动作：

- 在画布中选中一张图并点击“设为主图”
- 或上传一张图后直接声明它是主图

系统反馈：

- 明确高亮主图
- 显示“该图将作为分镜和连续性锚点”

### 步骤 2：发起分镜生成请求

用户动作：

- 在右侧对话框中输入中文需求
- 选择模式、镜头数、每镜候选数、比例、模型

系统反馈：

- 进入“主图解析 + 分镜规划”状态

### 步骤 3：展示分镜生成前 prompt 确认

系统展示：

- 中文展示 prompt
- 主图摘要
- 连续性摘要
- 预计生成规模
- 英文执行 prompt 折叠面板

用户操作：

- 确认生成
- 返回修改
- 取消

### 步骤 4：生成分镜结果

系统行为：

- 按 shot 生成图
- 每个 shot 按 variant 输出候选

系统反馈：

- 在画布中以 `shot × variant` 的结构呈现结果

### 步骤 5：查看与筛选分镜

用户动作：

- 浏览每个 shot 的候选图
- 选择喜欢的 variant

系统反馈：

- 标记每个 shot 的当前主版本

### 步骤 6：对单图进入多机位编辑

用户动作：

- 点击某个 variant，打开多机位编辑弹框

系统反馈：

- 弹框展示当前图、主图参考、当前 shot 信息、当前参数状态

### 步骤 7：在弹框中调整机位

用户动作：

- 拖动球体上的摄像机
- 调整水平环绕
- 调整垂直俯仰
- 调整景别缩放
- 点击预设视角后微调

系统反馈：

- 显示当前摄影语义
- 显示一致性优先的状态说明

### 步骤 8：生成单图新候选

用户动作：

- 点击“生成预览”或“正式生成”

系统行为：

- 在保持主体一致性的前提下生成 1 张或多张新候选

用户操作：

- 替换当前图
- 加入当前 shot 候选组
- 保留原图同时新增

### 步骤 9：发起视频生成

用户动作：

- 选中每个 shot 的主版本
- 点击生成视频

系统反馈：

- 进入视频前 prompt 确认

### 步骤 10：展示视频生成前 prompt 确认

系统展示：

- 中文视频 prompt
- 选中的首帧 / 中间帧 / 尾帧摘要
- 画面连续性摘要
- 视频参数摘要
- 英文执行 prompt 折叠面板

用户操作：

- 确认生成
- 返回修改
- 取消

## 15. 页面与状态设计

### 15.1 顶层状态机

```text
[Idle]
  |
  +--> [Main Image Selected]
  |        |
  |        +--> [Storyboard Drafting]
  |                 |
  |                 +--> [Prompt Confirm: Storyboard]
  |                           |
  |                           +--> [Storyboard Generating]
  |                                      |
  |                                      +--> [Storyboard Result Ready]
  |                                                 |
  |                                                 +--> [Single Frame Editing]
  |                                                 |
  |                                                 +--> [Video Prompt Drafting]
  |                                                              |
  |                                                              +--> [Prompt Confirm: Video]
  |                                                                         |
  |                                                                         +--> [Video Generating]
  |                                                                                    |
  |                                                                                    +--> [Video Result Ready]
  |
  +--> [Error / Cancel / Retry]
```

### 15.2 画布结构

建议以 `Shot × Variant` 组织，而不是散图平铺。

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 当前主图: [Image A]                                                          │
├──────────────────────────────────────────────────────────────────────────────┤
│ Shot 1  开场建立                                                             │
│   [S1V1 主版本]   [S1V2]   [S1V3]                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Shot 2  动作推进                                                             │
│   [S2V1 主版本]   [S2V2]   [S2V3]                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Shot 3  卖点强化                                                             │
│   [S3V1 主版本]   [S3V2]   [S3V3]                                            │
├──────────────────────────────────────────────────────────────────────────────┤
│ Shot 4  Hero 收束                                                            │
│   [S4V1 主版本]   [S4V2]   [S4V3]                                            │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 15.3 分镜 Prompt 确认面板

```text
┌───────────────────────────────────────┐
│ 生成前确认：分镜图                    │
│---------------------------------------│
│ 中文展示 Prompt                       │
│ “基于主图中的人物形象，生成一组...”   │
│---------------------------------------│
│ 主图摘要                              │
│ - 人物主体: 男孩                      │
│ - 风格: 写实棚拍                      │
│ - 连续性重点: 服装 / 发型 / 白底      │
│---------------------------------------│
│ 任务摘要                              │
│ - 模式: 线性分镜                      │
│ - 镜头数: 4                           │
│ - 每镜候选: 3                         │
│---------------------------------------│
│ [展开查看英文执行 Prompt]             │
│---------------------------------------│
│ [返回修改]   [取消]   [确认生成]      │
└───────────────────────────────────────┘
```

### 15.4 多机位编辑弹框

```text
┌──────────────────────────────────────────────────────────────────────────────┐
│ 多机位 / 多视角编辑器                                          [关闭]       │
├──────────────────────────────────────────────────────────────────────────────┤
│ 顶部预览区                                                                   │
│  [主图参考]   [当前图]   [最近候选]                                           │
├───────────────────────────────┬──────────────────────────────────────────────┤
│ 左侧：球体机位控件            │ 右侧：参数区                                 │
│                               │                                              │
│          ↑                    │ 预设视角                                     │
│      ←---O---→                │ [自定义] [左前45°] [俯拍] [仰拍] [背面]      │
│          ↓                    │                                              │
│                               │ 水平环绕   [====●======] 45°                │
│ 主体在中心                    │ 垂直俯仰   [==●========] -30°               │
│ 摄像机在球面                  │ 景别缩放   [=====●=====] 中景               │
│                               │ 一致性强度 [默认 ▼]                         │
│                               │ 背景保持   [开 / 关]                        │
│                               │ 提示词查看 [开 / 关]                        │
├───────────────────────────────┴──────────────────────────────────────────────┤
│ [重置参数]  [生成预览]  [正式生成]  [加入候选]  [替换当前图]                 │
└──────────────────────────────────────────────────────────────────────────────┘
```

### 15.5 弹框状态

建议至少支持：

- 初始态
- 已修改未生成态
- 预览生成中
- 预览成功
- 正式生成中
- 失败态

其中“加入候选”应作为默认更安全的主动作，“替换当前图”应视为更有风险的动作。

## 16. 技术设计总览

### 16.1 设计原则

- 复用现有模型能力
- 服务端编排优先
- 结构化中间层优先
- 候选生成优先

### 16.2 建议架构层

#### 输入层

负责接收：

- 用户自然语言
- 主图 / 首帧 file_id
- 当前画布上下文
- 分镜选择结果
- 单图机位参数

#### 理解与规划层

负责：

- 解析主图
- 理解任务意图
- 决定生成模式
- 生成分镜计划

#### 连续性建模层

负责：

- 提炼主图锚点
- 生成 Continuity Bible
- 将一致性约束应用到 shot 和 variant

#### Prompt 编译层

负责：

- 生成中文展示 prompt
- 生成英文执行 prompt
- 生成分镜前确认内容
- 生成视频前确认内容

#### 执行层

负责：

- 调用现有图像生成 / 编辑能力
- 批量生成分镜
- 生成单图多视角候选
- 调用现有视频能力

#### 回写与组织层

负责：

- 把图片回写到画布
- 为画布文件写入 generation meta 与 storyboard meta
- 组织 shot / variant 关系
- 为后续视频编译提供上下文

### 16.3 核心模块

- Main Image Analyzer
- Storyboard Planner
- Continuity Controller
- Variant Camera Compiler
- Dual Prompt Compiler
- Confirmation Orchestrator
- Storyboard Generation Runtime
- Single Frame Multiview Runtime
- Storyboard-to-Video Bridge

## 17. 关键对象与 schema 方向

以下对象是实现该方案时建议显式建模的核心对象。

### 17.1 MainImageAnchor

建议字段方向：

- anchor_id
- source_file_id
- subject_type
- subject_summary
- character_identity
- product_identity
- environment_identity
- lighting_identity
- style_identity
- suitable_generation_modes

### 17.2 ContinuityBible

建议字段方向：

- continuity_id
- anchor_id
- hard_constraints
- soft_constraints
- forbidden_drift
- allowed_variations

### 17.3 StoryboardPlan

建议字段方向：

- storyboard_id
- source_main_image_file_id
- mode
- aspect_ratio
- shot_count
- variant_count_per_shot
- continuity_id
- shots

### 17.4 Shot

建议字段方向：

- shot_id
- storyboard_id
- order_index
- narrative_role
- shot_goal
- continuity_anchor
- default_view
- allowed_views

### 17.5 Variant

建议字段方向：

- variant_id
- shot_id
- view_type
- azimuth
- elevation
- framing
- composition_priority
- is_primary
- source_prompt_bundle_id
- generated_file_id

### 17.6 CameraVariantSpec

建议字段方向：

- spec_id
- shot_id
- base_variant_id
- preset_name
- azimuth
- elevation
- framing
- emphasis
- keep_background
- consistency_strength

### 17.7 PromptBundle

建议字段方向：

- prompt_bundle_id
- task_type
- display_prompt_zh
- execution_prompt_en
- display_summary
- source_context
- editable
- confirmation_required

## 18. 生成链路与时序

### 18.1 主图 / 首帧 → 分镜

```text
Front-end
  -> Backend Entry
      -> MainImageAnalyzer
      -> StoryboardPlanner
      -> ContinuityController
      -> DualPromptCompiler
      -> ConfirmationOrchestrator
          -> Front-end Prompt Confirm UI
              -> user confirm
      -> StoryboardGenerationRuntime
          -> Image Generation Provider(s)
      -> Canvas Persistence
      -> WebSocket Update
  -> Front-end Canvas Refresh
```

### 18.2 单图多机位编辑

```text
Front-end Modal
  -> Backend Entry
      -> Load Current Variant Context
      -> VariantCameraCompiler
      -> DualPromptCompiler
      -> Optional Preview Confirmation
      -> SingleFrameMultiviewRuntime
          -> Image Edit / Reference Image Provider
      -> Canvas Persistence
      -> Variant Group Update
      -> WebSocket Update
  -> Front-end Modal Result
```

### 18.3 分镜 → 视频

```text
Front-end
  -> Backend Entry
      -> Load Selected Shot / Variant Set
      -> StoryboardToVideoBridge
      -> DualPromptCompiler
      -> ConfirmationOrchestrator
          -> Front-end Prompt Confirm UI
              -> user confirm
      -> Existing Video Runtime
      -> Canvas Persistence
      -> WebSocket Update
  -> Front-end Canvas Refresh
```

## 19. 双语 prompt 与确认机制

### 19.1 设计目标

保证：

- 用户看到的是中文、可读、可确认的 prompt
- 模型接收的是英文、适合执行的 prompt
- 两者来自同一个结构化中间层，而不是两份独立手写文本

### 19.2 建议做法

不建议简单“中文 prompt 直接翻译成英文 prompt”，而应采用：

结构化中间表示
→ 中文展示 prompt
→ 英文执行 prompt

### 19.3 确认节点

建议至少在以下两个任务中强制确认：

- storyboard_image_generation
- storyboard_to_video_generation

### 19.4 用户操作

建议统一为三个动作：

- 确认生成
- 返回修改
- 取消

后续可扩展：

- 编辑中文 prompt
- 重新编译英文 prompt

## 20. 元数据与结果组织

建议继续沿用“结果即上下文”的思路。

### 20.1 generationMeta 增补方向

- provider
- model
- aspect_ratio
- input_images
- prompt_bundle_id
- execution_prompt_en_snapshot

### 20.2 storyboardMeta 增补方向

- storyboard_id
- shot_id
- variant_id
- source_main_image_file_id
- continuity_id
- narrative_role
- view_type
- azimuth
- elevation
- framing
- display_prompt_zh_snapshot

### 20.3 结构关系

- 一个 storyboard 有多个 shot
- 一个 shot 有多个 variant
- 一个 variant 可对应一个或多个生成结果
- 每次单图重生成都应与原 shot 建立关联

## 21. MVP 范围

### 21.1 MVP 必做

- 主图锚点提取
- 线性分镜规划
- shot / variant 结构化组织
- continuity_bible 基础版
- 分镜前 prompt 确认
- 视频前 prompt 确认
- 中文展示 / 英文执行双轨 prompt
- 单图多机位基础参数：水平环绕、垂直俯仰、景别缩放
- 结果回流到当前 shot

### 21.2 MVP 暂不做

- 任意角度的高精度连续三维承诺
- 多主体复杂群像精修
- 用户直接编辑中文 prompt 并自动回编英文
- 自动三维重建
- 高级摄影参数如滚转、镜头畸变、透视强度深度控制
- 多步自动 QA 自愈闭环

## 22. 开发任务拆分

建议按以下 6 条工作流拆任务：

- 产品与交互
- 前端状态与组件
- 服务端编排与中间对象
- 图像生成链路
- 视频桥接链路
- 质量与验收

### 22.1 关键里程碑

#### M1：主图到分镜的中间层打通

输出：

- MainImageAnchor
- StoryboardPlan
- ContinuityBible
- PromptBundle
- 分镜前确认

#### M2：分镜结果组织与主版本选择

输出：

- `shot × variant` 结果组织
- 画布内主版本切换
- 结构化 metadata 回写

#### M3：单图多机位编辑弹框

输出：

- 弹框 UI
- 机位参数到 camera spec 的映射
- 单图候选生成
- 结果回流当前 shot

#### M4：分镜到视频确认链路

输出：

- 视频前确认
- 选中分镜到视频桥接
- continuity 与分镜上下文带入视频 prompt

### 22.2 MVP 任务列表

#### 产品与交互

- 定义主图概念与入口
- 定义分镜生成模式
- 定义 Prompt 确认面板
- 定义单图镜头编辑弹框

#### 前端

- 主图选定与状态管理
- 分镜请求面板
- Prompt 确认 UI
- Shot × Variant 结果视图
- 单图多机位编辑弹框
- 单图结果回流交互
- 视频生成入口增强

#### 服务端

- MainImageAnchor 服务
- ContinuityBible 服务
- StoryboardPlan 服务
- PromptBundle 服务
- Confirmation 编排服务
- Shot / Variant 组织服务

#### 图像生成链路

- 主图分镜生成运行时
- 双语 Prompt 编译
- 结果 metadata 回写
- CameraVariantSpec 编译
- 单图多机位生成运行时

#### 视频桥接

- 分镜主版本汇总
- 视频 PromptBundle 编译
- 视频生成链路接入

#### 质量验收

- 关键路径验收用例
- Prompt 确认体验验收
- 一致性体验验收
- 回流体验验收

## 23. 风险、边界与 Go / No-Go

### 23.1 能力边界

更适合：

- 主体明确的单人图
- 主体明确的单产品图
- 分镜导向的图像

不适合直接承诺精确效果：

- 多人复杂群像
- 遮挡极强
- 抽象风格过重
- 主体边界不清晰

### 23.2 模型风险

主要风险：

- 视角变化时人物漂移
- 服装和产品细节丢失
- 背景变化过大
- 同参数多次生成结果不稳定

应对思路：

- 候选优先
- 一致性优先
- 保留主版本
- 提供回退和重新选择

### 23.3 交互风险

主要风险：

- UI 看起来像真实 3D，但实际输出不稳定
- 用户对球体拖动的精确度期待过高

应对思路：

- 在产品语言上强调“镜头控制器”，而不是“3D 旋转器”
- 默认通过预设 + 微调工作，而不是强迫连续精准操作

### 23.4 Go / No-Go 条件

如果以下条件任一不满足，不建议直接开放完整功能：

- 分镜前 prompt 确认不可用
- 结果无法按 shot / variant 组织
- 单图编辑结果无法回流
- 视频前 prompt 确认不可用
- 一致性漂移严重到用户无法接受

## 24. 结论

本方案的关键，不在于简单复刻一个多角度 UI，而在于建立一套新的生成范式：

- 主图是母版
- 分镜是结构
- 多视角是镜头候选
- 连续性是底层规则
- 单图弹框是导演式精修器
- 右侧对话框是整组生成工作台
- 中文 prompt 用于用户确认
- 英文 prompt 用于模型执行

最终目标不是“让用户写更复杂的 prompt”，而是：

让用户以更接近镜头语言和导演语言的方式，控制主图扩展、分镜生成和多视角表达。

## 25. 开工前冻结清单

本节用于回答一个更实际的问题：

这份文档已经足够开工，但为了避免前后端、交互、服务端在实现过程中各自理解不同，建议在正式进入大规模开发前，先冻结以下关键决策。

这些决策不需要展开成长文档，但必须在团队内形成单一口径。

### 25.1 冻结目标

冻结清单的目标不是补充更多想法，而是：

- 压缩歧义
- 避免返工
- 让 MVP 的边界稳定下来

### 25.2 必须冻结的 12 个决策

#### FZ-1 主图的定义

必须明确：

- 主图是“视觉母版 + 连续性锚点 + 分镜起点”
- 主图不是普通参考图
- MVP 阶段一条分镜链路只允许一个主图

如果这一点不冻结，后续会出现“多张图都想当主图”的产品和技术歧义。

#### FZ-2 MVP 默认只做线性分镜

必须明确：

- MVP 不同时做“线性分镜”和“平行素材扩展”两套完整主链路
- MVP 的主路径是：
  - 主图
  - 线性分镜
  - 选中分镜
  - 生成视频

平行素材扩展可以保留为后续扩展方向，但不应在第一阶段稀释主链路。

#### FZ-3 默认分镜规模

必须明确一组默认值。

建议冻结为：

- 默认镜头数：4
- 默认每镜候选数：3

原因：

- 足够体现结构化分镜
- 成本和等待时间可控
- 便于前端先做 `shot × variant` 展示

#### FZ-4 Prompt 确认节点

必须明确：

- 分镜生成前必须确认
- 视频生成前必须确认
- 单图多机位编辑的“预览生成”阶段，MVP 不强制确认
- 单图多机位编辑的“正式生成”阶段，MVP 可不确认，直接走轻量生成

这样可以避免确认交互过多，先把高价值节点守住。

#### FZ-5 Prompt 确认时用户可做什么

必须明确：

- MVP 只支持：
  - 确认生成
  - 返回修改
  - 取消
- MVP 不支持在确认面板里直接编辑中文 prompt

原因：

- 一旦允许用户直接编辑中文 prompt，就会立刻引入中英重新编译、状态回写、版本一致性等一整套复杂度
- 这应作为第二阶段能力，而不是第一阶段前置要求

#### FZ-6 双语 prompt 的单一原则

必须明确：

- 用户默认只看中文 prompt
- 英文 prompt 默认折叠
- 中文和英文来自同一个结构化中间层
- 禁止“先写中文，再随意人工改一版英文”的双轨漂移

这是整个系统可信度的基础。

#### FZ-7 Shot 与 Variant 的最小规则

必须明确：

- 一个 shot 表示一个叙事职责
- 一个 shot 下至少有 1 个 variant，最多先展示 3 个 variant
- 每个 shot 在任意时刻必须有且仅有 1 个主版本

这条规则不冻结，前端展示和视频桥接都会很混乱。

#### FZ-8 画布中的最小展示规则

必须明确：

- 结果按 shot 分组
- 每组下展示 variant
- 主版本有明确高亮
- 新增 variant 默认追加到当前 shot 组内，而不是散落在画布里

MVP 阶段先不追求复杂布局系统，只保证结构可读。

#### FZ-9 多机位编辑的参数集合

必须明确：

- MVP 只开放 3 个主参数：
  - 水平环绕
  - 垂直俯仰
  - 景别缩放
- 只开放少量预设视角
- 不开放 roll、镜头畸变、透视强度、复杂背景控制等高级参数

否则参数集合会快速膨胀，影响交互稳定性和技术实现范围。

#### FZ-10 多机位参数的语义规则

必须明确：

- 水平环绕：前端可以连续拖动，但内部语义建议先归一到有限区段
- 垂直俯仰：建议先归一到有限档位
- 景别缩放：建议先归一到“特写 / 近景 / 中景 / 全身 / 远景”等离散语义

也就是说：

- UI 可以连续
- 内部语义应先离散

这是避免“看起来能精确控制，实际上完全不稳”的关键。

#### FZ-11 单图编辑结果的默认去向

必须明确：

- 默认推荐操作是“加入候选”
- “替换当前图”是次级、更有风险的动作
- 系统不应默认覆盖当前主版本

这条不冻结，用户很容易在单图编辑里误伤当前主分镜。

#### FZ-12 MVP 的能力承诺口径

必须明确统一对内口径：

- 我们做的是“镜头语义控制器”
- 不是“真实三维相机”
- 我们承诺的是“稳定的多视角候选生成”
- 不是“任意角度的精确 3D 还原”

这条必须在产品、设计、开发、测试之间完全一致，否则验收标准会错位。

### 25.3 推荐冻结值

为了更方便直接开工，建议用以下值作为默认冻结值。

#### 产品默认值

- 分镜模式：线性分镜
- 镜头数：4
- 每镜候选数：3
- 比例默认值：16:9

#### Prompt 确认默认值

- 分镜前：强制确认
- 视频前：强制确认
- 单图编辑：不强制确认

#### 单图多机位默认值

- 参数：水平环绕 / 垂直俯仰 / 景别缩放
- 预设：左前 45°、右前 45°、俯拍、仰拍、背面
- 结果默认操作：加入候选

#### 结果组织默认值

- 展示方式：`shot × variant`
- 每个 shot 一个主版本
- 新图默认追加到当前 shot

### 25.4 有了这份冻结清单后，哪些工作可以直接开工

冻结以上决策后，以下工作可以直接开工且返工风险较低：

- 主图状态与主图入口
- MainImageAnchor
- ContinuityBible 基础版
- StoryboardPlan
- PromptBundle
- 分镜前确认
- 视频前确认
- shot / variant 结构
- metadata 回写
- 右侧对话区主链路
- 单图弹框基础状态骨架

### 25.5 哪些工作仍然建议边做边验证

即使冻结了以上决策，下面这些仍建议边做边验证，而不是一开始就假设完全稳定：

- 球体控件的连续拖动体验
- 不同模型对多视角参数的响应稳定性
- 一致性控制在人物图与产品图上的差异
- 预设视角的命名是否符合用户直觉

### 25.6 最终结论

如果本节的 12 个决策都能冻结，那么这份综合文档就已经足够作为“正式开工文档”。

更具体地说：

- `M1` 可以直接开工
- `M2` 基本可以直接开工
- `M3` 可以在冻结参数语义后开工
- `M4` 可以随着 `M1/M2` 一起推进

也就是说，真正阻止开工的，不是方案本身不完整，而是这些关键决策如果不冻结，就容易在实现过程中反复改口。

## 26. 一步到位版本的最终蓝图

如果目标不是做过渡方案，而是尽量一步到位逼近 LibTV 这类产品体验，那么系统目标就不能停留在“主图触发更多图片生成”，而要升级为一套完整的“主图驱动的视频前生产系统”。

整体主线应定义为：

`主图 / 首帧`
→ `资产解析`
→ `用户确认`
→ `分镜规划`
→ `分镜生成`
→ `多视角展开`
→ `单镜微调`
→ `主版本确定`
→ `视频生成`

它的核心不是继续强化自然语言 prompt，而是围绕同一份 continuity 资产驱动后续所有任务。

### 26.1 三类核心资产

一步到位版本里，主图在进入分镜之前，应先被沉淀成三份核心资产：

- `Scene Bible`
- `Character Bible`
- `Camera Baseline`

#### Scene Bible

负责描述：

- 场景类型
- 空间结构
- 背景锚点
- 主道具
- 时间感
- 光线逻辑
- 不可变化项

#### Character Bible

负责描述：

- 角色身份
- 脸部特征
- 发型
- 服装
- 体态
- 不可漂移特征

#### Camera Baseline

负责描述：

- 主机位
- 主体朝向
- 镜头高度
- 初始景别
- 允许变化范围

### 26.2 系统目标的重新定义

一步到位版本的目标应明确为：

- 不是“从主图多生成几张图”
- 而是“围绕主图资产进行镜头规划、视角展开、局部修正和连续生成”

从产品哲学上，这意味着系统要从“图像生成工具”升级为“镜头组织系统”。

### 26.3 四层能力闭环

如果希望最终体验成立，那么必须一次性打通以下四层：

#### 资产层

先把主图变成可控资产，而不是直接拿去续写。

#### 规划层

先生成 shot plan，再生成实际镜头。

#### 生成层

从单张独立生成，升级为 continuity 驱动的整组生成和局部展开。

#### 交互层

用户确认的不是一句 prompt，而是一整套生产指令与镜头规划。

### 26.4 最终产品形态

用户看到的产品不应再只是：

- 一个输入框
- 一个生成按钮
- 一批返回图片

而应是：

- 一套主图 continuity 资产
- 一套镜头规划
- 一组按 shot 组织的分镜结果
- 一个可操作的多机位控制层
- 一个可回溯、可替换、可确定主版本的镜头编辑系统

## 27. 最终系统设计稿

本节用于把最终蓝图压缩成可开工的系统设计总纲，重点只覆盖三块：

- 模块边界
- 核心数据结构
- 用户主流程与异常流程

### 27.1 模块边界

建议按以下模块拆分。

#### Main Image Intake

职责：

- 设定主图 / 首帧
- 校验是否已有 continuity 资产
- 触发主图解析

输入：

- `canvas_id`
- `main_image_file_id`

输出：

- `continuity_asset_draft`

#### Continuity Analyzer

职责：

- 从主图提取 `Scene Bible / Character Bible / Camera Baseline`
- 生成中文展示摘要
- 生成英文执行上下文草稿

输入：

- 主图
- 主图原始生成信息
- 用户补充中文描述

输出：

- `scene_bible`
- `character_bible`
- `camera_baseline`
- `display_prompt_zh`
- `execution_context_en`

#### Continuity Confirmation

职责：

- 展示 continuity 草稿
- 接收确认 / 修改 / 取消
- 冻结 continuity 版本

输入：

- `continuity_asset_draft`

输出：

- `continuity_asset`

#### Storyboard Planner

职责：

- 基于 continuity 资产生成 shot plan
- 定义每镜职责、允许变化、继承关系、推荐机位

输入：

- `continuity_asset`
- 用户中文创意补充
- 镜头数、比例、候选数

输出：

- `storyboard_plan_draft`

#### Storyboard Confirmation

职责：

- 中文展示镜头规划
- 用户确认后再进入英文执行

输入：

- `storyboard_plan_draft`

输出：

- `storyboard_plan`

#### Storyboard Generator

职责：

- 根据 continuity 资产和 shot plan 生成整组分镜
- 为每镜生成主版本与候选版本
- 回写画布并保持组结构

输入：

- `continuity_asset`
- `storyboard_plan`

输出：

- `storyboard_shots`
- `storyboard_variants`

#### Multiview Controller

职责：

- 提供 3D 球机位控制
- 将自由交互吸附到标准机位格点
- 生成单镜多视角候选

输入：

- `shot_id`
- `variant_id`
- `camera_override`

输出：

- 新的 `storyboard_variant`

#### Shot Refinement

职责：

- 单镜头局部调整
- 替换当前图 / 加入候选 / 设为主版本
- 不破坏 continuity 和 shot 归属

输入：

- 单镜当前版本
- 用户修正意图

输出：

- 替换版或新增候选版

#### Video Prep

职责：

- 从已确认分镜汇总视频生成 brief
- 继承 continuity 资产
- 生成中文确认 / 英文执行 prompt

输入：

- 主版本分镜组
- continuity 资产

输出：

- `video_generation_brief`

### 27.2 核心数据结构

建议把 continuity 做成第一公民，而不是散在各处 metadata 中。

```ts
type ContinuityAsset = {
  continuity_id: string
  version: number
  source_main_image_file_id: string
  status: 'draft' | 'confirmed' | 'superseded'
  scene_bible: SceneBible
  character_bible: CharacterBible
  camera_baseline: CameraBaseline
  display_prompt_zh: string
  execution_context_en: string
  locked_rules: LockedRules
  allowed_variations: AllowedVariations
  created_at: number
  updated_at: number
}
```

```ts
type SceneBible = {
  scene_type: string
  location_summary_zh: string
  location_summary_en: string
  spatial_layout: string[]
  background_anchors: string[]
  prop_anchors: string[]
  time_of_day: string
  lighting_direction: string
  lighting_quality: string
  color_temperature: string
  mood_keywords: string[]
}
```

```ts
type CharacterBible = {
  subject_type: 'person' | 'product' | 'person_with_product'
  identity_label: string
  face_traits: string[]
  hair_traits: string[]
  body_traits: string[]
  wardrobe_traits: string[]
  product_traits: string[]
  non_drift_traits: string[]
  reference_token_en: string
}
```

```ts
type CameraBaseline = {
  facing_direction: string
  base_azimuth: number
  base_elevation: number
  base_framing: 'close' | 'medium' | 'full' | 'wide'
  lens_feel: string
  composition_notes: string[]
}
```

```ts
type LockedRules = {
  same_scene_required: boolean
  same_subject_required: boolean
  same_wardrobe_required: boolean
  same_lighting_logic_required: boolean
  background_anchor_locked: boolean
  prop_anchor_locked: boolean
}
```

```ts
type AllowedVariations = {
  camera_view: boolean
  framing: boolean
  pose: boolean
  expression: boolean
  minor_background_shift: boolean
  scene_change: boolean
}
```

```ts
type StoryboardPlan = {
  storyboard_id: string
  continuity_id: string
  aspect_ratio: string
  shot_count: number
  variant_count_per_shot: number
  shots: StoryboardShot[]
  display_prompt_zh: string
  execution_prompt_en: string
}
```

```ts
type StoryboardShot = {
  shot_id: string
  order_index: number
  narrative_role: string
  shot_goal_zh: string
  shot_goal_en: string
  inherits_from: 'main_image' | string
  locked_constraints: string[]
  allowed_variations: string[]
  camera_target: CameraTarget
  primary_variant_id?: string
}
```

```ts
type CameraTarget = {
  azimuth: number
  elevation: number
  framing: 'close' | 'medium' | 'full' | 'wide'
  preset_name: string
}
```

```ts
type StoryboardVariant = {
  variant_id: string
  storyboard_id: string
  shot_id: string
  continuity_id: string
  source_main_image_file_id: string
  source_variant_id?: string
  is_primary_variant: boolean
  generation_mode: 'storyboard' | 'multiview' | 'refinement'
  camera_target: CameraTarget
  display_prompt_zh_snapshot: string
  execution_prompt_en_snapshot: string
}
```

### 27.3 主流程

#### 主流程 A：主图到 continuity 资产

1. 用户在画布选择图片并设为主图。
2. 系统触发主图解析。
3. 系统生成 `Scene Bible + Character Bible + Camera Baseline` 草稿。
4. 聊天侧栏展示中文摘要：
   - 主体是谁
   - 场景是什么
   - 哪些必须不变
   - 哪些允许变化
5. 用户确认或修改。
6. 系统冻结 `continuity_asset`，生成英文执行上下文。

验收标准：

- 用户能明确看到系统理解的场景和角色。
- 用户能快速判断是否有误解。
- 后续所有分镜都绑定同一个 `continuity_id`。

#### 主流程 B：continuity 到分镜

1. 用户输入中文创意补充。
2. 系统基于 continuity 资产生成 shot plan。
3. 中文展示每镜职责、机位建议、允许变化。
4. 用户确认。
5. 系统按 shot plan 生成整组分镜。
6. 每镜生成主版本和候选版本。
7. 结果按 `storyboard_id + shot_id + variant_id` 回写画布。

验收标准：

- 生成结果默认属于同一场景家族。
- 每镜有明显叙事差异，但不是换世界。
- 每张图都能追溯到 `continuity_id` 和 `shot_id`。

#### 主流程 C：单镜多视角展开

1. 用户选择一个分镜主版本。
2. 打开多视角弹框。
3. 通过 3D 球拖动水平环绕角。
4. 通过侧边拖条调整仰视 / 平视 / 俯视。
5. 景别单独控制。
6. 系统将自由输入吸附到标准机位格点。
7. 生成新候选。
8. 用户选择：
   - 替换当前图
   - 加入候选
   - 设为主版本

验收标准：

- 变化主要体现在机位，不是场景重写。
- 新图仍属于原 `shot_id`。
- 用户能稳定做同镜多机位，而不是重新随机出图。

#### 主流程 D：分镜到视频

1. 用户在每镜选定主版本。
2. 系统汇总主版本分镜组。
3. 系统生成视频 brief。
4. 中文展示视频前确认内容。
5. 用户确认后，生成英文视频 prompt。
6. 视频生成继承同一个 `continuity_asset`。

验收标准：

- 视频阶段不重新发明角色和场景。
- 视频 prompt 明确引用 continuity 和 shot progression。
- 分镜到视频是一条连贯链路，而不是断开的两个功能。

### 27.4 异常流程

#### 主图解析不准

处理方式：

- 用户可直接修改中文资产摘要。
- 修改后重新生成 `execution_context_en`。
- 不要求用户手写英文。

#### 用户不想锁死场景

处理方式：

- 在 continuity 确认里允许关闭 `same_scene_required`。
- 但默认开启，并给出风险提示。

#### 某一镜生成跑偏

处理方式：

- 不重做整组。
- 进入单镜 refinement。
- 继承原 `shot_id` 和 `continuity_id` 局部重生。

#### 多视角结果不像同一镜

处理方式：

- 检查是否超出允许角度范围。
- 优先吸附离散格点而不是放任自由角度。
- 必要时回退到上一个主版本继续展开。

#### 视频前 continuity 丢失

处理方式：

- 视频生成只能基于已确认 continuity 资产。
- 如果主版本分镜存在多个 `continuity_id`，阻止提交并提示用户统一。

## 28. 接口设计

本节用于把系统设计稿继续落成“前后端如何通信”。

建议按以下五组接口拆分：

- `continuity`
- `storyboard`
- `multiview`
- `video`
- `confirmation`

### 28.1 continuity

```ts
POST /api/continuity/analyze
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  main_image_file_id: string
  prompt_zh?: string
}
```

返回：

```ts
{
  continuity_asset_draft: ContinuityAsset
}
```

用途：

- 基于主图生成 `Scene Bible / Character Bible / Camera Baseline`
- 返回中文展示内容和英文执行上下文草稿

```ts
POST /api/continuity/confirm
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_asset_draft: ContinuityAsset
  action: 'confirmed' | 'revise' | 'cancel'
}
```

返回：

```ts
{
  continuity_asset?: ContinuityAsset
  status: 'confirmed' | 'revise' | 'cancel'
}
```

用途：

- 用户确认 continuity
- 生成冻结版本，后续所有分镜和视频都引用 `continuity_id`

```ts
GET /api/continuity/:canvas_id/current
```

返回当前画布最新确认版 continuity。

这个接口很重要，因为画布刷新、重连、重新进入页面时，前端需要恢复当前项目的世界状态。

### 28.2 storyboard

```ts
POST /api/storyboard/plan
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  prompt_zh?: string
  shot_count: number
  variant_count_per_shot: number
  aspect_ratio: string
}
```

返回：

```ts
{
  storyboard_plan_draft: StoryboardPlan
}
```

用途：

- 先只生成镜头规划草稿
- 不直接生成图片

```ts
POST /api/storyboard/confirm
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  storyboard_plan_draft: StoryboardPlan
  action: 'confirmed' | 'revise' | 'cancel'
}
```

返回：

```ts
{
  storyboard_plan?: StoryboardPlan
  status: 'confirmed' | 'revise' | 'cancel'
}
```

```ts
POST /api/storyboard/generate
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  storyboard_id: string
}
```

返回建议走异步：

- HTTP 立即返回 `job_id`
- 实际进度通过 websocket 推送

websocket 事件建议：

```ts
storyboard_generation_started
storyboard_shot_started
storyboard_variant_created
storyboard_generation_completed
storyboard_generation_failed
```

这样前端才能在画布上逐张回写，用户体验也更像整组生产。

### 28.3 multiview

```ts
POST /api/multiview/generate
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  storyboard_id: string
  shot_id: string
  source_variant_id: string
  action_mode: 'append' | 'replace'
  camera_target: {
    azimuth: number
    elevation: number
    framing: 'close' | 'medium' | 'full' | 'wide'
    preset_name?: string
  }
  prompt_zh?: string
}
```

返回：

```ts
{
  job_id: string
}
```

关键约束：

- 必须要求 `shot_id`
- 必须要求 `source_variant_id`
- 必须要求 `continuity_id`

否则多视角就会退化成普通改图接口。

### 28.4 refinement

```ts
POST /api/storyboard/refine
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  storyboard_id: string
  shot_id: string
  source_variant_id: string
  mode: 'replace' | 'append'
  prompt_zh: string
}
```

用途：

- 单镜头局部调整
- 仍然挂在原 shot 下
- 不能生成游离候选

### 28.5 primary selection

```ts
POST /api/storyboard/variant/primary
```

请求体：

```ts
{
  canvas_id: string
  storyboard_id: string
  shot_id: string
  variant_id: string
}
```

用途：

- 设置某镜主版本
- 后续视频只读取每镜主版本

### 28.6 video prep

```ts
POST /api/video/brief
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  storyboard_id: string
  duration: number
  aspect_ratio: string
  resolution: string
}
```

返回：

```ts
{
  video_generation_brief_draft: VideoGenerationBrief
}
```

```ts
POST /api/video/confirm
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  video_generation_brief_draft: VideoGenerationBrief
  action: 'confirmed' | 'revise' | 'cancel'
}
```

```ts
POST /api/video/generate
```

请求体：

```ts
{
  canvas_id: string
  session_id: string
  continuity_id: string
  storyboard_id: string
  brief_id: string
}
```

### 28.7 前端事件与状态流

前端建议不要继续只靠零散的 event bus 字符串，最好为这套流程单独抽一个 `production workflow store`。

最少应维护以下状态：

```ts
type WorkflowState = {
  current_continuity_id?: string
  continuity_status: 'idle' | 'draft' | 'confirmed'
  storyboard_plan_status: 'idle' | 'draft' | 'confirmed' | 'generating'
  multiview_status: 'idle' | 'generating'
  video_brief_status: 'idle' | 'draft' | 'confirmed' | 'generating'
}
```

前端事件建议统一成：

```ts
Canvas::SetMainImage
Workflow::AnalyzeContinuity
Workflow::ConfirmContinuity
Workflow::PlanStoryboard
Workflow::ConfirmStoryboardPlan
Workflow::GenerateStoryboard
Workflow::GenerateMultiview
Workflow::RefineShot
Workflow::SetPrimaryVariant
Workflow::PrepareVideo
Workflow::ConfirmVideoBrief
Workflow::GenerateVideo
```

这样后续调试会比把状态分散在聊天组件、弹框组件和画布组件里更稳定。

## 29. 存储设计

核心原则只有一句：

`continuity` 资产不能只存在聊天消息里，也不能只存在单张图片 metadata 里，必须作为画布级资产单独落库。

### 29.1 canvas 级资产

如果希望尽量少动现有结构，建议先挂在 `canvas.data.production` 下：

```ts
type CanvasProductionState = {
  current_continuity_id?: string
  continuity_assets: Record<string, ContinuityAsset>
  storyboard_plans: Record<string, StoryboardPlan>
  video_briefs: Record<string, VideoGenerationBrief>
}
```

这样一个画布可以有多版 continuity，但同一时间只有一个 `current_continuity_id`。

### 29.2 file 级 metadata

每张图片继续保留 `storyboardMeta`，但建议升级为更稳定的结构：

```ts
type StoryboardMeta = {
  continuity_id: string
  storyboard_id: string
  shot_id: string
  variant_id: string
  source_main_image_file_id: string
  source_variant_id?: string
  generation_mode: 'storyboard' | 'multiview' | 'refinement'
  is_primary_variant: boolean
  camera_target: CameraTarget
  display_prompt_zh_snapshot: string
  execution_prompt_en_snapshot: string
}
```

这里要特别注意：

- `camera_target` 不要继续拆成很多松散字段，直接存对象
- `source_variant_id` 必须加，后续才能知道该候选是从哪一镜、哪一版衍生出来的

### 29.3 confirmation 级存储

当前待确认机制更像工具调用确认。一步到位版本里，建议把 confirmation 明确分型：

```ts
type ConfirmationRecord = {
  confirmation_id: string
  session_id: string
  canvas_id: string
  kind: 'continuity' | 'storyboard_plan' | 'video_brief'
  target_id: string
  payload: any
  status: 'pending' | 'confirmed' | 'revise' | 'cancel' | 'timeout'
  created_at: number
  updated_at: number
}
```

这样刷新页面时，前端可以恢复的不只是“有个待确认 prompt”，而是：

- 待确认的是 continuity
- 还是 storyboard plan
- 还是 video brief

### 29.4 版本与一致性策略

这里建议加一个硬规则：

- 每次确认 continuity，都产生一个新 `version`
- storyboard plan 必须绑定具体 `continuity_id + version`
- 分镜图必须绑定生成时的 continuity 版本
- 视频生成只能选择同一 `continuity_id + version` 下的主版本分镜

如果一组分镜混了多个 continuity 版本，系统应阻止直接生成视频，并提示用户统一版本。

### 29.5 推荐落库位置

如果当前数据库主要以 JSON 形式存储 canvas，那么建议：

- continuity asset
- storyboard plan
- video brief

都先落在 `canvas.data.production`。

这样做的优点是：

- 改动面最小
- 和画布天然同生命周期
- 回放、导出、复制画布时更容易保留上下文

等这套链路跑稳后，再考虑是否拆成独立表。

### 29.6 恢复接口

为保证流程可恢复，建议一次设计进以下恢复接口：

```ts
GET /api/workflow/:session_id/pending
GET /api/continuity/:canvas_id/current
GET /api/storyboard/:canvas_id/:storyboard_id
GET /api/video/brief/:canvas_id/current
```

目标是页面刷新后，前端能恢复三件事：

- 当前 continuity 是哪版
- 当前是否有待确认草稿
- 当前 storyboard 生成到了哪一镜

### 29.7 开工前最后要定的几件事

这几件事一旦定了，基本就可以拆任务：

1. continuity 是否作为画布级单独资产落库  
   建议：是，必须。

2. 分镜规划是否先确认再生成  
   建议：是，必须，不要回退成直接生成。

3. 多视角是否强制要求已有 `shot_id`  
   建议：是，必须，否则会失控。

4. 视频是否只读取每镜主版本  
   建议：是，必须，不要把候选混进去。

5. continuity 版本不一致时是否允许直接出视频  
   建议：不允许，必须拦截。

## 30. 实施任务拆分

本节将最终方案继续下沉为可分工、可排期、可验收的实施清单。

建议按四条线拆分：

- 前端
- 后端
- 数据迁移与存储
- 测试与验证

同时，建议再加一条横向约束：

- 所有任务都围绕 `continuity_asset` 这条主轴展开

也就是说，不能把“分镜”“多视角”“视频确认”分别做成三套平行逻辑，而必须共享同一套 continuity 数据与流程。

### 30.1 前端任务拆分

前端的目标不是只补几个按钮，而是把当前零散的交互整理成一条完整工作流。

#### FE-1 主图状态升级

目标：

- 将当前“设为主图”从单纯 file id 标记，升级为 continuity 工作流入口
- 主图变更时触发 continuity 分析逻辑

具体任务：

- 在画布上下文中保留 `current_main_image_file_id`
- 为主图入口接入 `Workflow::AnalyzeContinuity`
- 主图切换时清晰提示用户当前 continuity 是否会被重新建立

验收标准：

- 用户重新设置主图后，系统知道这不是普通图片选择，而是 continuity 源切换
- UI 上可清楚看到当前主图状态

#### FE-2 Production Workflow Store

目标：

- 建立独立的 workflow 状态层
- 不再只依赖零散 event bus 和局部组件状态

具体任务：

- 新建 workflow store
- 管理 `continuity_status`
- 管理 `storyboard_plan_status`
- 管理 `multiview_status`
- 管理 `video_brief_status`
- 管理 `current_continuity_id`

验收标准：

- 页面刷新恢复后，workflow 状态能够被重新同步
- 不同组件之间不再各自维护互相冲突的流程状态

#### FE-3 Continuity 确认卡片

目标：

- 在聊天侧栏中展示主图解析后的中文 continuity 资产

具体任务：

- 设计 continuity 确认卡片 UI
- 展示 `Scene Bible`
- 展示 `Character Bible`
- 展示 `Camera Baseline`
- 展示锁定项与允许变化项
- 提供 `确认 / 返回修改 / 取消`

验收标准：

- 用户能从中文卡片判断系统是否理解错了主图
- 用户无需读英文即可完成确认

#### FE-4 分镜规划确认卡片

目标：

- 在真正生成前，让用户先看中文 shot plan

具体任务：

- 展示镜头数、候选数、比例
- 展示每个 shot 的叙事职责
- 展示推荐机位和允许变化
- 展示 continuity 继承关系

验收标准：

- 用户看到的是“镜头规划”，不是最终英文 prompt 原文堆砌
- 用户能理解每镜为什么存在

#### FE-5 分镜结果的画布组织升级

目标：

- 将结果组织从“多张图散落在画布里”升级为明确的 `shot × variant` 结构

具体任务：

- 维持 shot 组边框和标签
- 高亮每镜主版本
- 新增候选默认追加到原 shot 组
- 区分 storyboard 主生成、多视角追加、refinement 追加

验收标准：

- 用户能一眼看懂哪些图属于同一镜
- 用户能一眼看懂哪张是当前主版本

#### FE-6 多视角弹框升级

目标：

- 把当前多视角面板升级成更接近 LibTV 交互语义的单镜编辑器

具体任务：

- 中央区域展示参考图与机位控制隐喻
- 提供水平环绕控制
- 提供垂直俯仰控制
- 提供景别控制
- 提供机位预设
- 明确 `替换当前图 / 加入候选 / 设为主版本`

验收标准：

- 交互语义清晰指向机位控制，而不是再次输入 prompt
- 用户能区分“生成新候选”和“覆盖当前结果”的风险

#### FE-7 单镜 refinement 弹框

目标：

- 将“多视角调整”和“局部改单镜”区分开

具体任务：

- 新增 refinement 输入区
- 支持中文改单镜说明
- 支持保留 continuity 锁定项展示
- 支持以当前 shot 作为上下文提交

验收标准：

- 用户改单镜时，不会误以为自己在重做整组分镜

#### FE-8 视频前确认升级

目标：

- 让视频前确认不仅展示一段文案，而是展示 continuity 继承关系和主版本分镜摘要

具体任务：

- 展示参与视频的主版本 shot 列表
- 展示时长、比例、分辨率
- 展示 continuity 摘要
- 展示中文视频 brief

验收标准：

- 用户能知道系统是基于哪些镜头去生成视频

#### FE-9 恢复与重连

目标：

- 保证刷新页面或 websocket 重连后，待确认工作流和当前 continuity 能恢复

具体任务：

- 页面初始化时拉取 current continuity
- 同步 pending confirmations
- 同步当前 storyboard plan
- 同步视频 brief draft

验收标准：

- 用户不会因为刷新页面而丢失流程上下文

### 30.2 后端任务拆分

后端的核心目标是把当前“直接生成图”的链路升级为“先资产化、再规划、再生成”的链路。

#### BE-1 Continuity Analyzer 服务

目标：

- 新增主图解析服务，输出结构化 continuity 资产草稿

具体任务：

- 定义 `ContinuityAsset` 服务对象
- 定义 `SceneBible`
- 定义 `CharacterBible`
- 定义 `CameraBaseline`
- 生成 `display_prompt_zh`
- 生成 `execution_context_en`

验收标准：

- 输出不再是几句泛化文本，而是有结构的 continuity 草稿

#### BE-2 Continuity Confirmation 服务

目标：

- 让 continuity 草稿可确认、可取消、可重新编辑

具体任务：

- 落库 continuity draft
- 处理 `confirmed / revise / cancel`
- 确认后生成 version
- 标记当前 `current_continuity_id`

验收标准：

- continuity 不再只存在瞬时 websocket 消息里

#### BE-3 Storyboard Planner 服务升级

目标：

- 从“默认 4 镜模板”升级为 continuity 驱动的 shot plan 生成

具体任务：

- shot 绑定 continuity
- 为每个 shot 输出中英文职责
- 输出 `inherits_from`
- 输出 `locked_constraints`
- 输出 `camera_target`

验收标准：

- shot plan 至少能表达“这镜为什么存在”和“这镜允许怎么变”

#### BE-4 Storyboard 生成链路升级

目标：

- 将 storyboard 生成与 continuity、shot plan 强绑定

具体任务：

- `/plan` 与 `/generate` 分离
- 生成前必须有 confirmed plan
- 每张结果回写 `continuity_id`
- 每张结果回写 `camera_target`
- 每张结果回写 `generation_mode`

验收标准：

- 分镜生成不再只是基于主图的独立重生成循环

#### BE-5 Multiview 生成链路升级

目标：

- 将多视角能力变成真正的 shot 内部衍生，而不是普通图生图

具体任务：

- 强制要求 `shot_id`
- 强制要求 `source_variant_id`
- 强制要求 `continuity_id`
- 保留 `source_variant_id` 血缘关系
- 支持 `append / replace`

验收标准：

- 多视角结果天然属于原 shot 组，而不是游离图片

#### BE-6 Refinement 生成链路

目标：

- 新增单镜头 refinement 服务

具体任务：

- 新增 refinement 请求入口
- 继承原 shot 的 continuity 约束
- 生成新 variant 或替换当前 variant

验收标准：

- 单镜微调与多视角控制分离，但共享 continuity 资产

#### BE-7 Video Brief 服务升级

目标：

- 视频阶段不再直接吃散乱的已选图片，而是吃主版本分镜组

具体任务：

- 汇总每镜主版本
- 校验所有主版本 continuity 是否一致
- 生成 `video_generation_brief_draft`
- 支持确认与取消

验收标准：

- 视频输入是结构化分镜组，而不是“若干刚好被选中的图片”

#### BE-8 Workflow Recovery 接口

目标：

- 为前端刷新恢复提供稳定接口

具体任务：

- `GET /api/continuity/:canvas_id/current`
- `GET /api/workflow/:session_id/pending`
- `GET /api/storyboard/:canvas_id/:storyboard_id`
- `GET /api/video/brief/:canvas_id/current`

验收标准：

- 页面刷新后，前端可以恢复主要工作流状态

### 30.3 数据迁移与存储任务拆分

数据层的目标不是单纯加字段，而是把 continuity 从隐式状态升级为显式资产。

#### DATA-1 canvas production state 落库

目标：

- 在画布级保存 production 数据

具体任务：

- 增加 `canvas.data.production`
- 存 `current_continuity_id`
- 存 `continuity_assets`
- 存 `storyboard_plans`
- 存 `video_briefs`

验收标准：

- 复制、恢复、导出画布时，production 上下文不会丢失

#### DATA-2 file metadata 升级

目标：

- 扩展图片的 `storyboardMeta`

具体任务：

- 增加 `continuity_id`
- 增加 `source_variant_id`
- 增加 `generation_mode`
- 增加 `camera_target`
- 规范化 prompt snapshot 字段

验收标准：

- 任意一张分镜图都可反查其 continuity、shot、来源 variant 和生成方式

#### DATA-3 confirmation record 分型

目标：

- 将待确认记录从单一工具确认，升级为流程级确认记录

具体任务：

- 加入 `kind`
- 加入 `target_id`
- 区分 `continuity / storyboard_plan / video_brief`

验收标准：

- 恢复逻辑不再只知道“有一个待确认”，而是知道“待确认的是什么”

#### DATA-4 continuity version 策略

目标：

- 确保 continuity 变更不会悄悄污染旧分镜

具体任务：

- continuity 确认产生 version
- storyboard plan 绑定 version
- variant 绑定 version
- video brief 校验 version 一致性

验收标准：

- 不同 continuity 版本的结果不会被系统误当成同一组资产

### 30.4 测试与验证任务拆分

这部分不能只做接口可用性验证，必须围绕“效果正确性”和“流程恢复能力”一起测。

#### QA-1 continuity 解析验证

验证重点：

- 是否能稳定生成 continuity draft
- 中文展示是否可读
- 用户是否能理解系统对主图的解释

验收样例：

- 人物主图
- 产品主图
- 人物 + 产品主图
- 室内场景
- 室外场景

#### QA-2 分镜规划验证

验证重点：

- shot plan 是否具备镜头职责差异
- 镜头规划是否仍然属于同一世界状态

验收样例：

- 4 镜广告分镜
- 6 镜剧情推进分镜
- 3 镜产品展示分镜

#### QA-3 同场景连续性验证

验证重点：

- 分镜生成是否默认保持同一场景
- 是否出现角色保住但场景换掉的情况
- 是否出现光线逻辑明显断裂

验收标准：

- 主图与分镜图之间的场景连续性明显优于当前版本

#### QA-4 多视角一致性验证

验证重点：

- 改变机位后，人物、服装、产品、场景是否仍然连续
- 多视角是否主要体现镜头变化，而不是内容漂移

验收样例：

- 左前 45°
- 右前 45°
- 俯拍
- 仰拍
- 全身
- 近景

#### QA-5 单镜 refinement 验证

验证重点：

- 单镜修正是否仍然挂在原 shot 下
- 替换当前图和加入候选是否行为正确

#### QA-6 视频前确认与生成验证

验证重点：

- 是否只读取每镜主版本
- continuity 不一致时是否拦截
- 视频 brief 是否继承 continuity 摘要

#### QA-7 刷新恢复与断线恢复验证

验证重点：

- continuity 待确认是否恢复
- storyboard plan 待确认是否恢复
- 视频 brief 待确认是否恢复
- 正在生成过程中的状态是否能重新同步

#### QA-8 有头浏览器回归

验证重点：

- 主图设置
- continuity 确认
- 分镜规划确认
- 分镜生成
- 单镜多视角
- 单镜 refinement
- 设为主版本
- 视频前确认

建议每次涉及流程变更后，都至少跑一轮有头浏览器主链路回归。

### 30.5 推荐实施顺序

即使目标是一步到位，实施上仍然建议有明确顺序，否则所有模块会互相阻塞。

#### 阶段 1：打通 continuity 主轴

优先完成：

- FE-1
- FE-2
- FE-3
- BE-1
- BE-2
- DATA-1
- DATA-3

阶段目标：

- 主图不再只是 file id，而是 continuity 资产入口

#### 阶段 2：打通 plan before generate

优先完成：

- FE-4
- BE-3
- BE-4
- DATA-2

阶段目标：

- 先确认 shot plan，再开始分镜生成

#### 阶段 3：打通 shot 内部编辑

优先完成：

- FE-5
- FE-6
- FE-7
- BE-5
- BE-6

阶段目标：

- 多视角和 refinement 都变成 shot 内操作

#### 阶段 4：打通视频闭环

优先完成：

- FE-8
- FE-9
- BE-7
- BE-8
- DATA-4

阶段目标：

- continuity 资产、分镜组、视频生成形成稳定闭环

### 30.6 最终验收口径

为了避免不同角色对“做完了”的理解不一致，建议用以下口径统一验收。

#### 产品层验收

- 用户能从主图建立 continuity 资产
- 用户能先确认镜头规划，再生成分镜
- 用户能在单镜上做多视角和 refinement
- 用户能明确选定每镜主版本
- 用户能基于主版本分镜生成视频

#### 技术层验收

- continuity 资产独立落库
- shot / variant / video brief 都绑定 continuity
- 页面刷新与恢复链路可用
- 不同 continuity 版本不会混用

#### 效果层验收

- 主图与分镜图场景连续性显著提升
- 多视角结果以机位变化为主，而不是内容漂移
- 视频前 prompt 与分镜 continuity 能保持一致
