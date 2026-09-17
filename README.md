# 文档互转网站 doc2doc-web

目标：在公网部署一个尽量免费的文档互转小网站，第一版支持：

- PDF → Word
- PDF → PPT
- Word → PDF
- PPT → PDF
- Word → PPT
- PPT → Word

## 本地运行

```powershell
cd doc2doc-web
.\start.ps1
```

打开 http://127.0.0.1:8000

如果你想手动执行而不使用脚本：

```powershell
cd doc2doc-web
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
python main.py
```

## 转换引擎说明

第一版优先使用本机/容器中的 LibreOffice 完成 PPT、Word、PDF 互转。若没有 LibreOffice，后端仍可启动，但除 PDF → Word 外的大部分转换会返回“未安装 LibreOffice”的失败原因，方便你本地知道还缺哪一步。

如果安装了 `pdf2docx`，PDF → Word 会优先使用该库，通常比直接让 LibreOffice 从 PDF 转 Word 更稳定。

## 质量说明

- Word → PDF、PPT → PDF：通常最稳定。
- PDF → Word、PDF → PPT：普通文档可用，复杂版式、扫描件、特殊字体建议下载后人工校对。
- 网站承诺是“高质量转换”，不是“无损转换”。

## 运行测试

```powershell
python -m pytest
```

## 部署到 Render

推荐用 Docker 方式部署，这样容器里会自动安装 LibreOffice：

1. 将 `doc2doc-web` 单独推到 GitHub 仓库。
2. 在 Render 创建 “Docker” 服务，选择该仓库。
3. Render 会自动识别根目录或子目录的 Dockerfile；如果选择子目录，把 Dockerfile 指向 `doc2doc-web/Dockerfile`。
4. 设置端口 `8000`。
5. 免费版 Render 可能休眠；再次访问时会唤醒。生产稳定运行建议后续升级到最低付费档。

如果使用 Render Python Web Service 而非 Docker：

- Build Command：`pip install -r requirements.txt pdf2docx`
- Start Command：`python main.py`
- 需要额外安装系统级 LibreOffice；Docker 方案更简单，推荐优先使用 Docker。

## 环境变量

- `PORT`：服务端口，本地默认 8000。
- `LIBREOFFICE_BIN`：可选，显式指定 soffice 路径。

## 技术要求

- Python 3.10 及以上
- 本地或容器安装 LibreOffice 后，6 个方向才都能转换
- `pdf2docx` 用于增强 PDF → Word 转换效果

## 上线操作清单（小白版）

### 1) 推到 GitHub
- 在 GitHub 新建一个私有或公开仓库，例如 `doc2doc-web`
- 在 `doc2doc-web` 目录执行：
  - `git init`
  - `git add .`
  - `git commit -m "doc2doc-web"`
  - `git remote add origin https://github.com/你的用户名/doc2doc-web.git`
  - `git push -u origin main`

### 2) 在 Render 建 Docker 服务
- 登录 Render
- `New` -> `Blueprint` 或 `New -> Docker Service`
- 连接你的 GitHub 仓库
- Root Directory 填：`doc2doc-web`
- Dockerfile 路径填：`Dockerfile`
- 端口填：`8000`
- 创建服务

### 3) 成本与限制
- Render 免费版可先用，但实例可能休眠
- 想要长期稳定在线，建议最低付费档
- 国内访问速度可能不稳定，这是平台限制，不是代码问题
