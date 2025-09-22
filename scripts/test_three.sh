#!/bin/bash
# scripts/test_stage3.sh
# Прогон всех ключевых сценариев Stage 2 + Stage 3 (без cat).
# Работает из любой директории.

set -euo pipefail

PY=python3
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
MAIN="$ROOT_DIR/main.py"
LOG="$ROOT_DIR/commands.xml"
VFS="$ROOT_DIR/vfs.xml"

run_case () {
  local title="$1"
  shift
  local tmp="$(mktemp /tmp/emulator_script.XXXXXX.txt)"
  cat > "$tmp" <<'EOF'
# Пусто
EOF
  # перезаписываем тем, что пришло в heredoc-аргумент
  cat > "$tmp" <<EOF
$@
EOF

  echo
  echo "=============================="
  echo "CASE: $title"
  echo "Script: $tmp"
  echo "=============================="

  $PY "$MAIN" "$@"   # сюда придут флаги/путь/скрипт из $@
  rm -f "$tmp" 2>/dev/null || true
}

# ---- CASE 1: Только логирование (Stage 2) ----
# Проверяем: --log, echo/ls/cd/unknowncmd, комментарии, exit.
tmp1="$(mktemp /tmp/emulator_script.XXXXXX.txt)"
cat > "$tmp1" <<'EOF'
# Демонстрация Stage 2: только лог
echo Stage2: привет
ls
cd demo
ls
unknowncmd
exit
EOF
echo "== CASE 1: --log =="
$PY "$MAIN" --log "$LOG" --script "$tmp1"
rm -f "$tmp1"

# ---- CASE 2: VFS + motd + лог (Stage 3) ----
# Проверяем: чтение VFS, motd, ls/cd по дереву, комментарии, exit.
tmp2="$(mktemp /tmp/emulator_script.XXXXXX.txt)"
cat > "$tmp2" <<'EOF'
# Демонстрация Stage 3: VFS из vfs.xml
# (без cat, как просили)
echo Stage3: начинаем
ls
cd home
ls
cd user
ls
cd projects
ls
echo Stage3: ок
exit
EOF
echo "== CASE 2: --vfs + --log + --script =="
$PY "$MAIN" --vfs "$VFS" --log "$LOG" --script "$tmp2"
rm -f "$tmp2"

# ---- CASE 3: Обработка ошибок (Stage 3) ----
# Проверяем: несуществующая команда и каталог, возврат на уровень вверх, продолжение работы.
tmp3="$(mktemp /tmp/emulator_script.XXXXXX.txt)"
cat > "$tmp3" <<'EOF'
# Ошибки и крайние случаи
echo Проверка ошибок
ls
cd nope
unknowncmd
cd home
cd user
ls
cd ..
ls
echo Готово
exit
EOF
echo "== CASE 3: error-handling on VFS =="
$PY "$MAIN" --vfs "$VFS" --log "$LOG" --script "$tmp3"
rm -f "$tmp3"

echo
echo "Все кейсы завершены. Лог смотри в: $LOG"
