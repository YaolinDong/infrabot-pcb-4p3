# 参与修改

欢迎提交问题、实物验证记录和可复核的改进。

报告硬件问题时，请提供 PCB 版本、核心板/屏幕型号、供电方式、装配范围、固件来源及可重现步骤；照片中请遮挡订单、地址或账号信息。

修改原生工程前另存自己的副本。电路、封装、位置或走线有变化时，应重新执行原生 ERC/DRC、重建铺铜，并同步生成对应 BOM/CPL/Gerber；不要把旧制造文件与新源工程混用。模型图不替代尺寸图和实物测量。

提交前运行：

```bash
python3 -B tools/verify.py
python3 -B -m unittest discover -s tests -v
```

如果修改了硬件，R8 固定清单校验失败是预期提醒，需要为新硬件版本补齐检查与制造依据。不要通过简单更新哈希隐藏未检查的设计变化。

提交信息采用英文 Conventional Commits，例如 `fix(pcb): correct connector pin mapping`、`docs(assembly): clarify LED2 lead forming`。设计变更、工具重构和纯文档修正尽量分别提交。

仅提交有权贡献的内容，按对应目录许可提供；复用第三方内容时保留原有声明并补充来源。不要提交 EDA 登录信息、本机桥接配置、订单资料、虚拟环境或临时产物。
