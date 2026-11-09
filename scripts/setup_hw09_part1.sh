
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WEB="$REPO/code/web_application"
VENV="$REPO/.venv"
DB_NAME="s6491_rel"
MONGO_NAME="s6491_mongo"
ENV_FILE="$WEB/.env"

step() { printf '\n==> %s\n' "$1"; }
die() { printf '\nERROR: %s\n' "$1" >&2; exit 1; }

if [ -z "${STUDENT_NAME:-}" ]; then
  read -r -p "Your full name (as on your HW8 PDF): " STUDENT_NAME
fi
[ -n "$STUDENT_NAME" ] || die "A name is required."
export STUDENT_NAME

step "Checking Docker"
docker info >/dev/null 2>&1 || die "Docker Desktop is not running. Start it, then run this script again."

step "Checking MySQL"
command -v mysql >/dev/null || die "mysql client not found. Install it with: brew install mysql"
mysql -u root -e "SELECT 1;" >/dev/null 2>&1 \
  || die "Cannot log in to MySQL as root. Start it with: brew services start mysql (set MYSQL_PWD if root has a password)."
mysql -u root -e "CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4;"
echo "database $DB_NAME is ready"

step "Writing $ENV_FILE"
if [ ! -f "$ENV_FILE" ]; then
  if [ -n "${MYSQL_PWD:-}" ]; then
    database_url="mysql+pymysql://root:${MYSQL_PWD}@127.0.0.1:3306/$DB_NAME"
  else
    database_url="mysql+pymysql://root@127.0.0.1:3306/$DB_NAME"
  fi
  printf 'DATABASE_URL=%s\n' "$database_url" > "$ENV_FILE"
  echo "created $ENV_FILE"
elif ! grep -q "/$DB_NAME" "$ENV_FILE"; then
  die "$ENV_FILE exists but does not point to $DB_NAME. Fix DATABASE_URL in that file, then run again."
else
  echo "$ENV_FILE already points to $DB_NAME, leaving it unchanged"
fi

step "Starting MongoDB"
if docker ps -a --format '{{.Names}}' | grep -qx "$MONGO_NAME"; then
  docker start "$MONGO_NAME" >/dev/null
else
  docker run -d --name "$MONGO_NAME" -p 27017:27017 mongo:7 >/dev/null
fi
for _ in $(seq 1 30); do
  if docker exec "$MONGO_NAME" mongosh --quiet --eval 'db.runCommand({ ping: 1 })' >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
echo "MongoDB is running"

step "Starting Redis"
docker compose -f "$WEB/docker-compose.redis.yml" up -d
docker exec s6491_redis redis-cli ping

step "Python environment"
if [ ! -x "$VENV/bin/python" ]; then
  python_bin="$(command -v python3.12 || command -v python3.11 || command -v python3)"
  "$python_bin" -m venv "$VENV"
fi
PY="$VENV/bin/python"
"$PY" -m pip install --quiet --upgrade pip
"$PY" -m pip install --quiet -r "$WEB/requirements.txt"
echo "packages installed"

step "Creating tables and seeding the three recalls"
(cd "$WEB" && "$PY" -c "import main")
mysql -u root "$DB_NAME" -e "SELECT id, recall_code, view_count FROM recalls;"

step "Running HW9 Part 1"
cd "$REPO"
"$PY" scripts/run_hw09_part1.py
