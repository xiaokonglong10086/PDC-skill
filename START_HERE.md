# PDC 快速开始

这是 PDC 公开 Beta 的最短可用路径。

## 1. 准备环境

需要：

- Git
- Python 3.11+
- Codex Desktop

确认：

```bash
git --version
python --version
```

Windows 也可以使用：

```powershell
py --version
```

## 2. 下载

```bash
git clone https://github.com/xiaokonglong10086/PDC-skill.git
cd PDC-skill
```

如果你下载的是 GitHub Release ZIP，解压后进入该目录即可。

## 3. 安装到 Codex Desktop

```bash
python scripts/pdc_first_run.py install
```

已有旧版时：

```bash
python scripts/pdc_first_run.py install --replace
```

替换前会备份已有本地安装。

## 4. 检查

```bash
python scripts/pdc_first_run.py doctor
```

机器可读结果：

```bash
python scripts/pdc_first_run.py doctor --json
```

## 5. 创建完全虚构的示例

```bash
python scripts/pdc_first_run.py demo
```

脚本会创建一个独立 Git 示例仓库和 PDC 控制状态，不需要你的真实项目数据。

然后在 Codex Desktop 打开脚本输出的示例目录，选择 PDC，并发送脚本打印出的提示词。

## 更新

拉取新的公开版本后：

```bash
git pull
python scripts/pdc_first_run.py install --replace
python scripts/pdc_first_run.py doctor
```

## 遇到问题

先查看 [`SUPPORT.md`](SUPPORT.md)。可复现 Bug 可以使用 GitHub Bug 模板提交。

**不要在公开 Issue 中粘贴密码、Token、私有仓库、客户数据或其他敏感信息。**
