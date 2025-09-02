from .system import system_info
from .rag import rag_query, rag_upsert
from .files import list_files, read_file, write_file

TOOL_REGISTRY = {
    "system_info": system_info,
    "rag_query": rag_query,
    "rag_upsert": rag_upsert,
    "list_files": list_files,
    "read_file": read_file,
    "write_file": write_file,
}
