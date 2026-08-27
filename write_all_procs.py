import psutil

if __name__ == "__main__":
    procs = []
    for proc in psutil.process_iter():
        try:
            procs.append(f"PID: {proc.pid} | Name: {proc.name()}")
        except Exception:
            pass
            
    with open("all_processes.txt", "w", encoding="utf-8") as f:
        f.write("\n".join(procs))
    print(f"已将 {len(procs)} 个进程写入 all_processes.txt")
