"""Public Docker runtime options shared by probe and managed helper."""
IMAGE = 'ai-search-vpn-spike:local'


def configure_managed_environment(tenant: str, vault: str) -> None:
    """Explicit probe opt-in, before Settings import; never changes SQL/env files."""
    import os
    from pathlib import Path
    if tenant.split('-')[0].lower() not in {'jhu', 'ju'}:
        raise ValueError('jhu_managed_local_only')
    os.environ.update(APP_ENV='local', TENANT_ID=tenant, JHU_CONNECTION_MODE='managed',
                      JHU_KEY_VAULT_NAME=vault,
                      JHU_API_USERNAME_SECRET='ju-ai-search-jhu-api-username-prod',
                      JHU_API_PASSWORD_SECRET='ju-ai-search-jhu-api-password-prod',
                      JHU_HELPER_WORKSPACE=str(Path(__file__).resolve().parents[2]))


def container_command(name: str, mode: str) -> list[str]:
    command = ['docker', 'run', '--pull', 'never', '--rm', '--name', name, '-i', '--user', '65532:65532',
               '--cap-drop', 'ALL', '--security-opt', 'no-new-privileges', '--read-only',
               '--pids-limit', '64', '--memory', '512m', '--cpus', '0.5',
               '--log-driver', 'none', '--tmpfs',
               '/run/probe:rw,noexec,nosuid,size=1m,uid=65532,gid=65532,mode=0700']
    if mode == 'offline':
        command += ['--network', 'none']
    return command + [IMAGE, mode]
