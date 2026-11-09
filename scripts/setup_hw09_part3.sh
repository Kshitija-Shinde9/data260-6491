
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/code/web_application"
VENV="$REPO/.venv"
COMPOSE="$WEB/docker-compose.redis.yml"

step() { printf '\n==> %s\n' "$1"; }
die() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Docker"
docker info >/dev/null 2>&1 || die "Docker Desktop is not running. Start it, then run this script again."

step "Checking Redis Stack"
running_image="$(docker inspect -f '{{.Config.Image}}' s6491_redis 2>/dev/null || true)"
if [ -z "$running_image" ] || [[ "$running_image" != redis/redis-stack-server:* ]]; then
  echo "starting Redis Stack as s6491_redis"
  docker rm -f s6491_redis >/dev/null 2>&1 || true
  docker compose -f "$COMPOSE" up -d
fi
ready=""
for _ in $(seq 1 30); do
  if docker exec s6491_redis redis-cli MODULE LIST 2>/dev/null | grep -q search; then
    ready=1
    break
  fi
  sleep 1
done
[ -n "$ready" ] || die "Redis Stack is not serving the search module."
docker exec s6491_redis redis-cli ping

step "Checking MySQL recalls"
command -v mysql >/dev/null || die "mysql client not found."
mysql -u root -e "SELECT id, recall_code, affected_units FROM s6491_rel.recalls;" \
  || die "Cannot read s6491_rel. Run bash scripts/setup_hw09_part1.sh once."

step "Checking Ollama"
ollama_tags="$(curl -sf http://127.0.0.1:11434/api/tags || true)"
[ -n "$ollama_tags" ] || die "Ollama is not answering on port 11434. Open the Ollama app."
case "$ollama_tags" in
  *'"qwen3:8b"'*) echo "qwen3:8b is available" ;;
  *) die "qwen3:8b is not pulled. Run: ollama pull qwen3:8b" ;;
esac

step "Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python_bin="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$python_bin" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$WEB/requirements.txt"
echo "packages installed"

step "Running HW9 Part 3"
cd "$REPO"
"$PY" scripts/run_hw09_part3.py
