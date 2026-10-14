#!/usr/bin/env bash
# classfiles integrity guard.
#
# WHY THIS EXISTS (2026-10-13): the teacher portal's 教材庫 read /api/fm/list, which lists
# CLASSDIR/<level>/<section>. The four material sections of L1..L4 — teacher / student / software / ai —
# DISAPPEARED from /var/www/iits/classfiles between 00:56 and 06:45 that morning: a logged download of
# L1/teacher/創意製造 · 15_直昇機_演示課件.pptx returned 200 and 48,837,257 bytes at 00:56, and by 06:49
# the only thing left under each level was `lessons/`. Every 教材庫 tab therefore rendered 尚無檔案.
#
# The shape a healthy level has (verified against the live tree):
#   L1/{ai,software,teacher,student,lessons}   L4/... (yai: teacher/ + student/ only)
# A level also carries its per-lesson stage dirs at the root (201-bp01 …, assets/), so the real
# child count is 36–38, not five. The assertions below key on the NAMED sections and lessons/ being
# present (and above their floors), never on the child count, so they hold either way.
# The failure mode is an rsync --delete whose SOURCE is a built lesson stage (which contains only
# lessons/ + assets/) applied to the LEVEL ROOT instead of to ../lessons/. Such a delete removes the
# four material sections and leaves lessons/ looking perfect — which is why it is invisible until a
# teacher opens 教材庫.
#
# Run BEFORE and AFTER any deploy that touches /var/www/iits/classfiles.
# Exit code 0 = shape intact; 1 = something is missing (do not proceed, do not call the deploy done).
set -u
CD=/var/www/iits/classfiles
SECS="teacher student software ai"
LEVS="L1 L2 L3 L4 yai"
MIN="teacher:60 student:10 software:4 ai:1"   # floor per section, so an empty dir also fails
fail=0

echo "=== classfiles integrity: $CD ==="
# L1..L4 carry all five children; yai is a different course and legitimately has teacher/ + student/
# only (its software/ is a symlink into L1/software, and it has no lessons/).
for lv in $LEVS; do
  printf "%-4s children=%-3s : " "$lv" "$(ls -d "$CD/$lv"/*/ 2>/dev/null | wc -l)"
  if [ "$lv" = "yai" ]; then
    for s in teacher student; do
      if [ -d "$CD/$lv/$s" ]; then printf "%s(%s) " "$s" "$(find "$CD/$lv/$s" -maxdepth 1 -type f 2>/dev/null | wc -l)"
      else printf "%s✗ " "$s"; fail=1; fi
    done
    echo
    continue
  fi
  for s in $SECS; do
    if [ -d "$CD/$lv/$s" ]; then
      printf "%s(%s) " "$s" "$(find "$CD/$lv/$s" -maxdepth 1 -type f 2>/dev/null | wc -l)"
    else
      printf "%s✗ " "$s"
      fail=1
    fi
  done
  # lessons/ must survive every deploy
  [ -d "$CD/$lv/lessons" ] || { printf "lessons✗ "; fail=1; }
  echo
  # per-section floors, so a silently-emptied dir is caught too
  for pair in $MIN; do
    s=${pair%%:*}; m=${pair##*:}
    [ -d "$CD/$lv/$s" ] || continue
    n=$(find "$CD/$lv/$s" -maxdepth 1 -type f 2>/dev/null | wc -l)
    if [ "$n" -lt "$m" ]; then
      echo "     !! $lv/$s has $n files, below the floor of $m — treat as data loss"
      fail=1
    fi
  done
done

echo
if [ "$fail" = 0 ]; then
  echo "==> OK: every level carries its material sections and lessons/"
else
  echo "==> DAMAGED: a material section is missing or emptied."
  echo "    Restore from the last pre-damage backup, e.g.:"
  echo "      tar -xzf ~/backups/iits-lessons-all-20261012-174048.tgz \\"
  echo "        --wildcards 'classfiles/L*/teacher/*' 'classfiles/L*/student/*' \\"
  echo "                     'classfiles/L*/software/*' 'classfiles/L*/ai/*'"
  echo "      sudo rsync -a --no-perms --no-owner --no-group --ignore-existing \\"
  echo "        <stage>/classfiles/L1/teacher/ $CD/L1/teacher/     # NEVER --delete"
fi
exit $fail
