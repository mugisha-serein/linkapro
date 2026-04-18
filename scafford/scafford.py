from pathlib import Path


BASE = Path(__file__).resolve().parent

DIRECTORIES = [
    "domain/identity",
    "domain/events",
    "domain/documents",
    "domain/vendors",
    "domain/marketplace",
    "domain/governance",
    "application/identity",
    "application/events",
    "application/documents",
    "application/vendors",
    "application/marketplace",
    "application/governance",
    "django_app/settings",
    "django_app/identity",
    "django_app/events",
    "django_app/documents",
    "django_app/vendors",
    "django_app/governance",
    "fastapi_app/marketplace",
    "infrastructure/repos",
    "infrastructure/adapters",
    "tasks",
    "templates/exports",
]

PLACEHOLDER_FILES = {
    "README.md": "# Project Scaffold\n",
    "docker-compose.yml": "# Scaffold placeholder for future service definitions.\n",
    "Dockerfile.django": "# Scaffold placeholder for the Django image.\n",
    "Dockerfile.fastapi": "# Scaffold placeholder for the FastAPI image.\n",
    "nginx.conf": "# Scaffold placeholder: /admin/* /api/django/* -> Django | /api/v1/* -> FastAPI\n",
    "templates/exports/.gitkeep": "",
}

PYTHON_PACKAGE_DIRS = [
    "domain",
    "domain/identity",
    "domain/events",
    "domain/documents",
    "domain/vendors",
    "domain/marketplace",
    "domain/governance",
    "application",
    "application/identity",
    "application/events",
    "application/documents",
    "application/vendors",
    "application/marketplace",
    "application/governance",
    "django_app",
    "django_app/settings",
    "django_app/identity",
    "django_app/events",
    "django_app/documents",
    "django_app/vendors",
    "django_app/governance",
    "fastapi_app",
    "fastapi_app/marketplace",
    "infrastructure",
    "infrastructure/repos",
    "infrastructure/adapters",
    "tasks",
]


def ensure_directory(relative_path: str) -> None:
    (BASE / relative_path).mkdir(parents=True, exist_ok=True)


def write_text_file(relative_path: str, content: str) -> bool:
    path = BASE / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        return False

    path.write_text(content, encoding="utf-8")
    return True


def main() -> None:
    created_directories = 0
    created_files = 0

    for directory in DIRECTORIES:
        path = BASE / directory
        existed = path.exists()
        ensure_directory(directory)
        if not existed:
            created_directories += 1

    for relative_path, content in PLACEHOLDER_FILES.items():
        if write_text_file(relative_path, content):
            created_files += 1

    for package_dir in PYTHON_PACKAGE_DIRS:
        if write_text_file(f"{package_dir}/__init__.py", ""):
            created_files += 1

    print(
        f"Scaffold ready in {BASE} "
        f"({created_directories} directories created, {created_files} files created)."
    )


if __name__ == "__main__":
    main()
