
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/code/web_application"
VENV="$REPO/.venv"
COMPOSE="$WEB/docker-compose.redis.yml"

step() { printf '\n==> %s\n' "$1"; }
die() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

step "Checking Docker"
docker info >/dev/null 2>&1 || die "Docker Desktop is not running. Start it, then run this script again."

step "Starting Redis Stack (same container name s6491_redis, port 6379)"

running_image="$(docker inspect -f '{{.Config.Image}}' s6491_redis 2>/dev/null || true)"
if [ -n "$running_image" ] && [[ "$running_image" != redis/redis-stack-server:* ]]; then
  echo "replacing $running_image with Redis Stack"
  docker rm -f s6491_redis >/dev/null
fi
docker compose -f "$COMPOSE" up -d
ready=""
for _ in $(seq 1 30); do
  if docker exec s6491_redis redis-cli MODULE LIST 2>/dev/null | grep -q search; then
    ready=1
    break
  fi
  sleep 1
done
[ -n "$ready" ] || die "Redis Stack did not load the search module."
docker exec s6491_redis redis-cli ping

step "Checking MySQL recalls"
command -v mysql >/dev/null || die "mysql client not found."
mysql -u root -e "SELECT COUNT(*) AS recalls FROM s6491_rel.recalls;" \
  || die "Cannot read s6491_rel. Start MySQL, then run bash scripts/setup_hw09_part1.sh once."

step "Checking Ollama"
if ! curl -sf http://127.0.0.1:11434/api/tags >/dev/null; then
  die "Ollama is not running. In another terminal: ollama serve"
fi
if ! curl -sf http://127.0.0.1:11434/api/tags | grep -q 'qwen3:8b'; then
  die "qwen3:8b is not pulled. Run: ollama pull qwen3:8b"
fi
echo "qwen3:8b is available"

step "Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python_bin="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$python_bin" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$WEB/requirements.txt"
echo "packages installed"

step "Running HW9 Part 2"
cd "$REPO"
"$PY" scripts/run_hw09_part2.py
