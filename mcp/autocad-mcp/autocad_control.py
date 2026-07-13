#!/usr/bin/env python3
"""
AutoCAD COM 自动化控制模块
通过 win32com 控制 AutoCAD 进行图层/样式/系统变量等配置操作

用法:
  python autocad_control.py layer list                           # 列出所有图层
  python autocad_control.py layer create <name> [options]         # 创建图层
  python autocad_control.py layer delete <name>                   # 删除图层
  python autocad_control.py layer set <name> [options]            # 修改图层属性
  python autocad_control.py layer batch <json_file>               # 批量创建图层 (JSON)
  python autocad_control.py style text list                       # 列出文字样式
  python autocad_control.py style text create <name> [options]    # 创建文字样式
  python autocad_control.py style dim list                        # 列出标注样式
  python autocad_control.py style dim create <name> [options]     # 创建标注样式
  python autocad_control.py linetype list                         # 列出已加载线型
  python autocad_control.py linetype load <name>                  # 加载线型
  python autocad_control.py sysvar get <name>                     # 读系统变量
  python autocad_control.py sysvar set <name> <value>             # 写系统变量
  python autocad_control.py preset layers [--gb]                  # 预设图层方案
  python autocad_control.py preset dimstyle [--arch]              # 预设标注样式
  python autocad_control.py info                                  # 显示当前图纸信息
"""

import argparse
import json
import sys
import os
from collections import OrderedDict

# ── 颜色常量 ────────────────────────────────────────────
COLOR_INDEX = {
    "byblock": 0, "red": 1, "yellow": 2, "green": 3, "cyan": 4,
    "blue": 5, "magenta": 6, "white": 7, "bylayer": 256,
    "8": 8, "9": 9, "dark_red": 10, "dark_yellow": 11, "dark_green": 12,
    "dark_cyan": 13, "dark_blue": 14, "dark_magenta": 15,
}

# ── 线宽常量 ────────────────────────────────────────────
LINEWEIGHT = {
    "bylayer": -3, "byblock": -2, "default": -1,
    "0.00": 0, "0.05": 5, "0.09": 9, "0.13": 13, "0.15": 15,
    "0.18": 18, "0.20": 20, "0.25": 25, "0.30": 30, "0.35": 35,
    "0.40": 40, "0.50": 50, "0.53": 53, "0.60": 60, "0.70": 70,
    "0.80": 80, "0.90": 90, "1.00": 100, "1.06": 106,
    "1.20": 120, "1.40": 140, "1.58": 158, "2.00": 200, "2.11": 211,
}


class AutoCADController:
    """AutoCAD COM 控制器"""

    def __init__(self):
        self.acad = None
        self.doc = None
        self._connect()

    def _connect(self):
        """连接到 AutoCAD（优先已运行的实例）"""
        import win32com.client
        try:
            self.acad = win32com.client.GetActiveObject("AutoCAD.Application")
        except Exception:
            # 尝试各版本 ProgID
            for ver in [26, 25, 24, 23]:
                try:
                    self.acad = win32com.client.Dispatch(f"AutoCAD.Application.{int(ver)}")
                    self.acad.Visible = True
                    break
                except Exception:
                    continue
            if not self.acad:
                raise RuntimeError("无法连接到 AutoCAD，请确保 AutoCAD 已安装")
        self.doc = self.acad.ActiveDocument
        if not self.doc:
            # 如果没有打开的文档，创建一个
            self.doc = self.acad.Documents.Add()

    def _reconnect_if_needed(self):
        """如果 COM 断开则重连"""
        try:
            _ = self.doc.Name
        except Exception:
            self._connect()

    # ─── 信息 ──────────────────────────────────────────

    def get_info(self):
        """获取当前图纸基本信息"""
        self._reconnect_if_needed()
        info = OrderedDict()
        info["version"] = self.acad.Version
        info["drawing"] = self.doc.Name
        info["path"] = self.doc.Path
        info["layer_count"] = self.doc.Layers.Count
        info["text_style_count"] = self.doc.TextStyles.Count
        info["dim_style_count"] = self.doc.DimStyles.Count
        info["block_count"] = self.doc.Blocks.Count
        # 图形界限
        try:
            limits = self.doc.GetVariable("LIMMIN"), self.doc.GetVariable("LIMMAX")
            info["limits"] = f"({limits[0]:.0f},{limits[1]:.0f})"
        except Exception:
            info["limits"] = "N/A"
        return info

    # ─── 图层管理 ──────────────────────────────────────

    def list_layers(self):
        """列出所有图层"""
        self._reconnect_if_needed()
        layers = []
        for i in range(self.doc.Layers.Count):
            layer = self.doc.Layers.Item(i)
            layers.append({
                "name": layer.Name,
                "color_index": layer.TrueColor.ColorIndex if hasattr(layer, 'TrueColor') and layer.TrueColor else layer.Color,
                "linetype": layer.Linetype,
                "lineweight": self._lw_to_str(layer.Lineweight),
                "on": layer.LayerOn,
                "freeze": layer.Freeze,
                "lock": layer.Lock,
                "description": layer.Description if hasattr(layer, 'Description') else "",
            })
        return layers

    def create_layer(self, name, color="7", linetype="Continuous",
                     lineweight="default", on=True, freeze=False,
                     lock=False, description="", plot=True):
        """创建图层"""
        self._reconnect_if_needed()
        # 检查是否已存在
        try:
            existing = self.doc.Layers.Item(name)
            return {"status": "skipped", "reason": f"图层 '{name}' 已存在", "layer": existing.Name}
        except Exception:
            pass

        layer = self.doc.Layers.Add(name)

        # 颜色: 支持数字字符串和颜色名
        if color:
            if isinstance(color, str) and color.lower() in COLOR_INDEX:
                ci = COLOR_INDEX[color.lower()]
            else:
                try:
                    ci = int(color)
                except ValueError:
                    ci = 7
            layer.TrueColor.ColorIndex = ci

        # 线型
        if linetype:
            try:
                layer.Linetype = linetype
            except Exception:
                # 可能线型未加载，尝试加载
                try:
                    self.doc.Linetypes.Load(linetype, "acad.lin")
                    layer.Linetype = linetype
                except Exception:
                    pass  # 保持默认线型

        # 线宽
        if lineweight:
            lw = self._parse_lw(lineweight)
            layer.Lineweight = lw

        layer.LayerOn = on
        layer.Freeze = freeze
        layer.Lock = lock
        if hasattr(layer, 'Description') and description:
            layer.Description = description

        if hasattr(layer, 'Plottable'):
            layer.Plottable = plot

        return {"status": "created", "name": name, "color": color, "linetype": linetype}

    def delete_layer(self, name):
        """删除图层（不能删除 0 层和 Defpoints）"""
        self._reconnect_if_needed()
        if name in ("0", "Defpoints"):
            return {"status": "error", "reason": f"不能删除图层 '{name}'"}
        try:
            layer = self.doc.Layers.Item(name)
            layer.Delete()
            return {"status": "deleted", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def set_layer(self, name, **kwargs):
        """修改图层属性"""
        self._reconnect_if_needed()
        try:
            layer = self.doc.Layers.Item(name)
        except Exception as e:
            return {"status": "error", "reason": f"图层 '{name}' 不存在: {e}"}

        changes = {}
        if "color" in kwargs and kwargs["color"] is not None:
            c = kwargs["color"]
            if isinstance(c, str) and c.lower() in COLOR_INDEX:
                ci = COLOR_INDEX[c.lower()]
            else:
                try:
                    ci = int(c)
                except ValueError:
                    ci = 7
            layer.TrueColor.ColorIndex = ci
            changes["color"] = ci

        if "linetype" in kwargs and kwargs["linetype"]:
            try:
                layer.Linetype = kwargs["linetype"]
                changes["linetype"] = kwargs["linetype"]
            except Exception:
                pass

        if "lineweight" in kwargs and kwargs["lineweight"] is not None:
            lw = self._parse_lw(kwargs["lineweight"])
            layer.Lineweight = lw
            changes["lineweight"] = kwargs["lineweight"]

        if "on" in kwargs and kwargs["on"] is not None:
            layer.LayerOn = kwargs["on"]
            changes["on"] = kwargs["on"]

        if "freeze" in kwargs and kwargs["freeze"] is not None:
            layer.Freeze = kwargs["freeze"]
            changes["freeze"] = kwargs["freeze"]

        if "lock" in kwargs and kwargs["lock"] is not None:
            layer.Lock = kwargs["lock"]
            changes["lock"] = kwargs["lock"]

        if "description" in kwargs:
            if hasattr(layer, 'Description'):
                layer.Description = kwargs["description"] or ""
                changes["description"] = kwargs["description"]

        return {"status": "updated", "name": name, "changes": changes}

    def set_current_layer(self, name):
        """设为当前图层"""
        self._reconnect_if_needed()
        try:
            self.doc.ActiveLayer = self.doc.Layers.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def batch_create_layers(self, layer_defs):
        """批量创建图层
        layer_defs: [{"name": "...", "color": "...", "linetype": "...", "lineweight": "..."}, ...]
        """
        results = []
        for ld in layer_defs:
            name = ld.pop("name")
            r = self.create_layer(name, **ld)
            results.append(r)
        return results

    # ─── 文字样式 ────────────────────────────────────

    def list_text_styles(self):
        self._reconnect_if_needed()
        styles = []
        for i in range(self.doc.TextStyles.Count):
            s = self.doc.TextStyles.Item(i)
            styles.append({
                "name": s.Name,
                "font_file": s.FontFile,
                "big_font_file": s.BigFontFile if hasattr(s, 'BigFontFile') else "",
                "height": s.Height,
                "width": s.Width,
                "oblique_angle": s.ObliqueAngle,
            })
        return styles

    def create_text_style(self, name, font="arial.ttf", big_font="",
                          height=0.0, width=1.0, oblique_angle=0.0):
        """创建文字样式（高度=0 表示使用时再指定）"""
        self._reconnect_if_needed()
        try:
            existing = self.doc.TextStyles.Item(name)
            return {"status": "skipped", "reason": f"文字样式 '{name}' 已存在"}
        except Exception:
            pass

        style = self.doc.TextStyles.Add(name)
        # SetFont(fontFile, bold, italic, charSet, pitchAndFamily)
        # charSet: 0=Ansi, 1=Default, 2=Symbol, 128=ShiftJIS, 134=GB2312
        charset = 134  # GB2312 中文字符集
        style.SetFont(font, False, False, charset, 34)
        if big_font:
            style.BigFontFile = big_font
        if height > 0:
            style.Height = height
        style.Width = width
        style.ObliqueAngle = oblique_angle
        return {"status": "created", "name": name, "font": font}

    def set_current_text_style(self, name):
        self._reconnect_if_needed()
        try:
            self.doc.ActiveTextStyle = self.doc.TextStyles.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ─── 标注样式 ────────────────────────────────────

    def list_dim_styles(self):
        self._reconnect_if_needed()
        styles = []
        for i in range(self.doc.DimStyles.Count):
            s = self.doc.DimStyles.Item(i)
            styles.append({"name": s.Name})
        return styles

    def create_dim_style(self, name, copy_from="Standard"):
        """创建标注样式（从现有样式复制）"""
        self._reconnect_if_needed()
        try:
            existing = self.doc.DimStyles.Item(name)
            return {"status": "skipped", "reason": f"标注样式 '{name}' 已存在"}
        except Exception:
            pass

        src = self.doc.DimStyles.Item(copy_from)
        dims = self.doc.DimStyles.Add(name)
        dims.CopyFrom(src)
        return {"status": "created", "name": name, "copied_from": copy_from}

    def set_dim_vars(self, style_name, **variables):
        """设置标注样式的变量
        常用变量:
        DIMTXT — 文字高度
        DIMASZ — 箭头大小
        DIMEXE — 尺寸界线超出量
        DIMEXO — 尺寸界线起点偏移量
        DIMDLI — 基线标注间距
        DIMSCALE — 全局比例因子
        DIMLUNIT — 线性标注单位 (2=小数)
        DIMDEC — 小数位数
        DIMDSEP — 小数分隔符
        DIMTIH — 文字在尺寸界线内是否水平放置 (0=对齐, 1=水平)
        DIMTOH — 文字在尺寸界线外是否水平放置
        """
        self._reconnect_if_needed()
        # 先设为当前标注样式，然后设置变量
        self.doc.ActiveDimStyle = self.doc.DimStyles.Item(style_name)
        for var, val in variables.items():
            self.acad.SetVariable(var, val)
        return {"status": "updated", "style": style_name, "variables": variables}

    def set_current_dim_style(self, name):
        self._reconnect_if_needed()
        try:
            self.doc.ActiveDimStyle = self.doc.DimStyles.Item(name)
            return {"status": "current", "name": name}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    # ─── 线型管理 ────────────────────────────────────

    def list_linetypes(self):
        self._reconnect_if_needed()
        lts = []
        for i in range(self.doc.Linetypes.Count):
            lt = self.doc.Linetypes.Item(i)
            lts.append({"name": lt.Name, "description": lt.Description})
        return lts

    def load_linetype(self, name, file="acad.lin"):
        """加载线型"""
        self._reconnect_if_needed()
        try:
            self.doc.Linetypes.Load(name, file)
            return {"status": "loaded", "name": name}
        except Exception as e:
            # 可能已加载
            for i in range(self.doc.Linetypes.Count):
                if self.doc.Linetypes.Item(i).Name == name:
                    return {"status": "already_loaded", "name": name}
            return {"status": "error", "reason": str(e)}

    # ─── 系统变量 ────────────────────────────────────

    def get_sysvar(self, name):
        self._reconnect_if_needed()
        try:
            return {"name": name, "value": self.acad.GetVariable(name)}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def set_sysvar(self, name, value):
        self._reconnect_if_needed()
        try:
            self.acad.SetVariable(name, value)
            return {"status": "set", "name": name, "value": value}
        except Exception as e:
            return {"status": "error", "reason": str(e)}

    def set_sysvars_batch(self, variables):
        """批量设置系统变量"""
        results = []
        for k, v in variables.items():
            results.append(self.set_sysvar(k, v))
        return results

    # ─── 预设方案 ────────────────────────────────────

    def preset_gb_layers(self):
        """GB/T 建筑图层标准预设"""
        layers = [
            {"name": "A-AXIS", "color": "1", "description": "轴线", "linetype": "CENTER"},
            {"name": "A-WALL", "color": "7", "description": "墙体"},
            {"name": "A-WALL-PART", "color": "8", "description": "隔墙"},
            {"name": "A-COLUMN", "color": "2", "description": "柱"},
            {"name": "A-DOOR", "color": "4", "description": "门"},
            {"name": "A-WINDOW", "color": "4", "description": "窗"},
            {"name": "A-STAIR", "color": "3", "description": "楼梯"},
            {"name": "A-DIM", "color": "3", "description": "尺寸标注", "lineweight": "0.15"},
            {"name": "A-TEXT", "color": "7", "description": "文字", "lineweight": "0.15"},
            {"name": "A-HATCH", "color": "8", "description": "填充图案", "lineweight": "0.09"},
            {"name": "A-FURN", "color": "8", "description": "家具"},
            {"name": "A-SANIT", "color": "4", "description": "卫生洁具"},
            {"name": "A-ELEC", "color": "6", "description": "电气"},
            {"name": "A-PIPE", "color": "5", "description": "管道"},
            {"name": "A-EQPM", "color": "2", "description": "设备"},
            {"name": "A-ELEV", "color": "1", "description": "标高", "lineweight": "0.15"},
            {"name": "A-SYMB", "color": "2", "description": "符号", "lineweight": "0.15"},
            {"name": "A-VPORT", "color": "8", "description": "视口", "plot": False},
        ]
        # 先加载 CENTER 线型
        self.load_linetype("CENTER")
        return self.batch_create_layers(layers)

    def preset_dim_style_arch(self, name="建筑标注-1:100", scale=100):
        """预设建筑标注样式"""
        result = self.create_dim_style(name)
        if result["status"] != "created":
            return result

        vars_to_set = {
            "DIMSCALE": scale,
            "DIMTXT": 3.5 * scale / 100,
            "DIMASZ": 2.5 * scale / 100,
            "DIMEXE": 2.0 * scale / 100,
            "DIMEXO": 1.5 * scale / 100,
            "DIMDLI": 7.0 * scale / 100,
            "DIMLUNIT": 2,
            "DIMDEC": 0,
            "DIMDSEP": ord('.'),
            "DIMTIH": 0,
            "DIMTOH": 0,
            "DIMZIN": 8,  # 不显示末尾零
        }
        self.set_dim_vars(name, **vars_to_set)
        return {"status": "created", "name": name, "scale": scale, "variables": vars_to_set}

    # ─── 辅助方法 ────────────────────────────────────

    @staticmethod
    def _lw_to_str(lw_val):
        """线宽数值 → 字符串"""
        if lw_val == -3:
            return "ByLayer"
        if lw_val == -2:
            return "ByBlock"
        if lw_val == -1:
            return "Default"
        return f"{lw_val / 100:.2f}mm"

    @staticmethod
    def _parse_lw(lw_str):
        """线宽字符串 → 数值"""
        if isinstance(lw_str, (int, float)):
            return int(lw_str)
        key = lw_str.lower()
        if key in LINEWEIGHT:
            return LINEWEIGHT[key]
        try:
            mm = float(lw_str)
            return int(mm * 100)
        except ValueError:
            return -1


# ══════════════════════════════════════════════════════════
# CLI 入口
# ══════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="AutoCAD COM 自动化控制")
    sub = parser.add_subparsers(dest="cmd", help="命令")

    # ── layer ──
    layer_parser = sub.add_parser("layer", help="图层管理")
    layer_subs = layer_parser.add_subparsers(dest="action")

    lp_list = layer_subs.add_parser("list", help="列出所有图层")

    lp_create = layer_subs.add_parser("create", help="创建图层")
    lp_create.add_argument("name", help="图层名称")
    lp_create.add_argument("--color", "-c", default="7", help="颜色 (索引号或颜色名)")
    lp_create.add_argument("--linetype", "-lt", default="Continuous", help="线型名称")
    lp_create.add_argument("--lineweight", "-lw", default="default", help="线宽 (mm 或 bylayer/byblock/default)")
    lp_create.add_argument("--off", action="store_true", help="关闭图层")
    lp_create.add_argument("--freeze", action="store_true", help="冻结图层")
    lp_create.add_argument("--lock", action="store_true", help="锁定图层")
    lp_create.add_argument("--description", "-d", default="", help="图层说明")
    lp_create.add_argument("--no-plot", action="store_true", help="不打印")

    lp_delete = layer_subs.add_parser("delete", help="删除图层")
    lp_delete.add_argument("name", help="图层名称")

    lp_set = layer_subs.add_parser("set", help="修改图层属性")
    lp_set.add_argument("name", help="图层名称")
    lp_set.add_argument("--color", "-c", help="颜色")
    lp_set.add_argument("--linetype", "-lt", help="线型")
    lp_set.add_argument("--lineweight", "-lw", help="线宽")
    lp_set.add_argument("--on", type=int, choices=[0, 1], help="开/关")
    lp_set.add_argument("--freeze", type=int, choices=[0, 1], help="冻结/解冻")
    lp_set.add_argument("--lock", type=int, choices=[0, 1], help="锁定/解锁")
    lp_set.add_argument("--description", "-d", help="图层说明")

    lp_current = layer_subs.add_parser("current", help="设为当前图层")
    lp_current.add_argument("name", help="图层名称")

    lp_batch = layer_subs.add_parser("batch", help="批量创建图层 (JSON 文件或 JSON 字符串)")
    lp_batch.add_argument("input", help="JSON 文件路径 或 JSON 字符串")

    # ── style ──
    style_parser = sub.add_parser("style", help="样式管理")
    style_subs = style_parser.add_subparsers(dest="style_type")

    # style text
    st_parser = style_subs.add_parser("text", help="文字样式管理")
    st_subs = st_parser.add_subparsers(dest="action")

    st_list = st_subs.add_parser("list", help="列出文字样式")

    st_create = st_subs.add_parser("create", help="创建文字样式")
    st_create.add_argument("name", help="样式名称")
    st_create.add_argument("--font", "-f", default="arial.ttf", help="字体文件 (默认 Arial, 中文可用 simsun.ttf)")
    st_create.add_argument("--big-font", "-bf", default="", help="大字体文件 (中文通常用 gbcbig.shx)")
    st_create.add_argument("--height", "-ht", type=float, default=0.0, help="字体高度 (0=使用时指定)")
    st_create.add_argument("--width", "-w", type=float, default=1.0, help="宽度因子")
    st_create.add_argument("--oblique", "-o", type=float, default=0.0, help="倾斜角度（度）")

    st_current = st_subs.add_parser("current", help="设为当前文字样式")
    st_current.add_argument("name", help="样式名称")

    # style dim
    sd_parser = style_subs.add_parser("dim", help="标注样式管理")
    sd_subs = sd_parser.add_subparsers(dest="action")

    sd_list = sd_subs.add_parser("list", help="列出标注样式")

    sd_create = sd_subs.add_parser("create", help="创建标注样式")
    sd_create.add_argument("name", help="样式名称")
    sd_create.add_argument("--copy-from", "-cf", default="Standard", help="从哪个样式复制 (默认 Standard)")

    sd_set = sd_subs.add_parser("set-vars", help="设置标注变量")
    sd_set.add_argument("name", help="标注样式名称")
    sd_set.add_argument("--txt-height", type=float, help="DIMTXT: 文字高度")
    sd_set.add_argument("--arrow-size", type=float, help="DIMASZ: 箭头大小")
    sd_set.add_argument("--scale", type=float, help="DIMSCALE: 全局比例")
    sd_set.add_argument("--decimals", type=int, help="DIMDEC: 小数位数")

    sd_current = sd_subs.add_parser("current", help="设为当前标注样式")
    sd_current.add_argument("name", help="样式名称")

    # ── linetype ──
    lt_parser = sub.add_parser("linetype", help="线型管理")
    lt_subs = lt_parser.add_subparsers(dest="action")

    lt_list = lt_subs.add_parser("list", help="列出已加载线型")
    lt_load = lt_subs.add_parser("load", help="加载线型")
    lt_load.add_argument("name", help="线型名称 (如 CENTER, HIDDEN, DASHED)")
    lt_load.add_argument("--file", default="acad.lin", help="线型文件")

    # ── sysvar ──
    sv_parser = sub.add_parser("sysvar", help="系统变量管理")
    sv_subs = sv_parser.add_subparsers(dest="action")

    sv_get = sv_subs.add_parser("get", help="读取系统变量")
    sv_get.add_argument("name", help="变量名称 (如 DIMSCALE, LTSCALE, OSMODE)")

    sv_set = sv_subs.add_parser("set", help="设置系统变量")
    sv_set.add_argument("name", help="变量名称")
    sv_set.add_argument("value", help="变量值")

    # ── preset ──
    preset_parser = sub.add_parser("preset", help="预设方案")
    preset_subs = preset_parser.add_subparsers(dest="preset_type")

    pr_layer = preset_subs.add_parser("layers", help="预设图层方案")
    pr_layer.add_argument("--gb", action="store_true", default=True, help="GB/T 建筑图层标准 (默认)")

    pr_dim = preset_subs.add_parser("dimstyle", help="预设标注样式")
    pr_dim.add_argument("--arch", action="store_true", default=True, help="建筑标注样式 (默认)")
    pr_dim.add_argument("--name", default="建筑标注-1:100", help="样式名称")
    pr_dim.add_argument("--scale", type=int, default=100, help="比例因子")

    # ── info ──
    sub.add_parser("info", help="显示当前图纸信息")

    args = parser.parse_args()
    if not args.cmd:
        parser.print_help()
        return

    ctrl = AutoCADController()
    result = _dispatch(ctrl, args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return result


def _dispatch(ctrl, args):
    """分发命令到控制器方法"""
    cmd = args.cmd
    action = getattr(args, "action", None)

    if cmd == "info":
        return ctrl.get_info()

    if cmd == "layer":
        if action == "list":
            return ctrl.list_layers()
        elif action == "create":
            return ctrl.create_layer(
                name=args.name, color=args.color,
                linetype=args.linetype, lineweight=args.lineweight,
                on=not args.off, freeze=args.freeze,
                lock=args.lock, description=args.description,
                plot=not args.no_plot,
            )
        elif action == "delete":
            return ctrl.delete_layer(args.name)
        elif action == "set":
            kwargs = {}
            for attr in ["color", "linetype", "lineweight", "on", "freeze", "lock", "description"]:
                val = getattr(args, attr, None)
                if val is not None:
                    kwargs[attr] = val
            return ctrl.set_layer(args.name, **kwargs)
        elif action == "current":
            return ctrl.set_current_layer(args.name)
        elif action == "batch":
            return _handle_batch(ctrl, args.input)

    if cmd == "style":
        stype = args.style_type
        if stype == "text":
            if action == "list":
                return ctrl.list_text_styles()
            elif action == "create":
                return ctrl.create_text_style(
                    name=args.name, font=args.font,
                    big_font=args.big_font, height=args.height,
                    width=args.width, oblique_angle=args.oblique,
                )
            elif action == "current":
                return ctrl.set_current_text_style(args.name)

        elif stype == "dim":
            if action == "list":
                return ctrl.list_dim_styles()
            elif action == "create":
                return ctrl.create_dim_style(args.name, args.copy_from)
            elif action == "set-vars":
                variables = {}
                if args.txt_height is not None:
                    variables["DIMTXT"] = args.txt_height
                if args.arrow_size is not None:
                    variables["DIMASZ"] = args.arrow_size
                if args.scale is not None:
                    variables["DIMSCALE"] = args.scale
                if args.decimals is not None:
                    variables["DIMDEC"] = args.decimals
                if variables:
                    return ctrl.set_dim_vars(args.name, **variables)
                return {"status": "error", "reason": "没有指定要修改的变量"}
            elif action == "current":
                return ctrl.set_current_dim_style(args.name)

    if cmd == "linetype":
        if action == "list":
            return ctrl.list_linetypes()
        elif action == "load":
            return ctrl.load_linetype(args.name, args.file)

    if cmd == "sysvar":
        if action == "get":
            return ctrl.get_sysvar(args.name)
        elif action == "set":
            # 尝试类型转换
            val = args.value
            try:
                val = int(val)
            except ValueError:
                try:
                    val = float(val)
                except ValueError:
                    pass
            return ctrl.set_sysvar(args.name, val)

    if cmd == "preset":
        ptype = args.preset_type
        if ptype == "layers":
            return ctrl.preset_gb_layers()
        elif ptype == "dimstyle":
            return ctrl.preset_dim_style_arch(args.name, args.scale)

    return {"status": "error", "reason": "未知命令"}


def _handle_batch(ctrl, input_str):
    """处理批量图层创建"""
    # 尝试作为文件路径
    if os.path.isfile(input_str):
        with open(input_str, "r", encoding="utf-8") as f:
            data = json.load(f)
    else:
        data = json.loads(input_str)
    if isinstance(data, dict) and "layers" in data:
        data = data["layers"]
    return ctrl.batch_create_layers(data)


if __name__ == "__main__":
    main()
