"""
脚本功能：将当前目录下所有子文件夹中的Python文件（.py）合并到一个文档中
使用方法：直接运行此脚本，会在当前目录生成 all_py_files.txt 文件
作者备注：可用于代码备份、代码审查或AI辅助分析等场景
"""

import os

# ==================== 配置参数 ====================
output_file = "all_py_files.txt"      # 输出的文件名
current_dir = "."                       # 当前目录（"."表示脚本所在的目录）
# =================================================

# 打开输出文件（使用utf-8编码，支持中文）
with open(output_file, "w", encoding="utf-8") as out_f:
    
    # os.walk 会遍历当前目录及其所有子目录
    # root: 当前正在遍历的文件夹路径
    # dirs: 当前文件夹下的子文件夹列表
    # files: 当前文件夹下的文件列表
    for root, dirs, files in os.walk(current_dir):
        
        # 遍历当前文件夹中的所有文件
        for file in files:
            
            # 只处理以 .py 结尾的文件
            if file.endswith(".py"):
                
                # 获取文件的完整路径
                file_path = os.path.join(root, file)
                
                # 在输出文件中添加分隔线，标明文件来源
                out_f.write(f"\n{'='*60}\n")
                out_f.write(f"File: {file_path}\n")      # 写入文件路径
                out_f.write(f"{'='*60}\n\n")
                
                # 尝试读取并写入文件内容
                try:
                    # 以只读方式打开Python文件（使用utf-8编码）
                    with open(file_path, "r", encoding="utf-8") as in_f:
                        out_f.write(in_f.read())          # 写入文件全部内容
                except Exception as e:
                    # 如果读取失败（如编码错误、权限问题等），记录错误信息
                    out_f.write(f"Error reading file: {e}\n")
                
                # 文件内容后面加两个换行，便于区分不同文件
                out_f.write("\n\n")

# 运行完成后提示用户
print(f"完成！所有Python文件已合并到 {output_file}")

# ==================== 附加功能：仅生成文件清单 ====================
# 如果只需要文件名清单（不需要内容），可以用下面的代码替换上面的内容

with open("py_files_list.txt", "w", encoding="utf-8") as f:
    for root, dirs, files in os.walk("."):
        for file in files:
            if file.endswith(".py"):
                f.write(os.path.join(root, file) + "\n")

print("文件清单已生成到 py_files_list.txt")

