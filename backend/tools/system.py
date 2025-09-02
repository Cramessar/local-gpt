import platform, psutil, datetime

def system_info(**kwargs):
    return {
        "os": platform.platform(),
        "python": platform.python_version(),
        "cpu_percent": psutil.cpu_percent(interval=0.2),
        "memory": dict(total=psutil.virtual_memory().total, percent=psutil.virtual_memory().percent),
        "time": datetime.datetime.now().isoformat(),
    }
