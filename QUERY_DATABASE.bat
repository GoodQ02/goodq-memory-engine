@echo off
chcp 65001 > nul
setlocal EnableDelayedExpansion

echo.
echo ╔═══════════════════════════════════════════════════════════════╗
echo ║          🔍 GoodQ Database Query Tool                         ║
echo ╚═══════════════════════════════════════════════════════════════╝
echo.

cd /d L:\goodq4all

:menu
echo.
echo Select query type:
echo.
echo   [1] Scene Summary (count, duration, video info)
echo   [2] Sample Captions (first 10 scenes with descriptions)
echo   [3] Search by Keyword (find scenes containing text)
echo   [4] Timeline View (scenes in chronological order)
echo   [5] Embedding Statistics (by modality)
echo   [6] Knowledge Graph Stats
echo   [7] Export Scene List to JSON
echo   [0] Exit
echo.
set /p choice="Enter choice: "

if "%choice%"=="1" goto scene_summary
if "%choice%"=="2" goto sample_captions
if "%choice%"=="3" goto search_keyword
if "%choice%"=="4" goto timeline
if "%choice%"=="5" goto embeddings
if "%choice%"=="6" goto knowledge_graph
if "%choice%"=="7" goto export_scenes
if "%choice%"=="0" goto end
goto menu

:scene_summary
echo.
echo === Scene Summary ===
python -c "import sqlite3; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT COUNT(*), MIN(start), MAX(end) FROM scenes'); row = c.fetchone(); print(f'Total scenes: {row[0]}'); print(f'Duration: {row[1]:.1f}s to {row[2]:.1f}s ({(row[2]-row[1])/60:.1f} minutes)'); c.execute('SELECT video_hash, COUNT(*) FROM scenes GROUP BY video_hash'); print('\nVideos:'); [print(f'  {vid}: {cnt} scenes') for vid, cnt in c.fetchall()]; conn.close()"
pause
goto menu

:sample_captions
echo.
echo === Sample Captions ===
python -c "import sqlite3, json; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT start, end, meta FROM scenes ORDER BY start LIMIT 10'); print('\nFirst 10 scenes:\n'); [print(f'{i+1}. {start:.1f}s-{end:.1f}s: {json.loads(meta).get(\"caption\", \"(no caption)\")}') for i, (start, end, meta) in enumerate(c.fetchall()) if meta]; conn.close()"
pause
goto menu

:search_keyword
echo.
set /p keyword="Enter search keyword: "
echo.
echo === Searching for "%keyword%" ===
python -c "import sqlite3, json; keyword = '%keyword%'; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT start, end, meta FROM scenes'); results = [(start, end, meta) for start, end, meta in c.fetchall() if meta and keyword.lower() in json.loads(meta).get('caption', '').lower()]; print(f'\nFound {len(results)} scenes:\n'); [print(f'{start:.1f}s-{end:.1f}s: {json.loads(meta).get(\"caption\")}') for start, end, meta in results[:20]]; conn.close()"
pause
goto menu

:timeline
echo.
echo === Timeline View ===
python -c "import sqlite3, json; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT start, end, meta FROM scenes ORDER BY start LIMIT 20'); print('\nTimeline (first 20 scenes):\n'); [print(f'{int(start//60):02d}:{int(start%%60):02d} - {json.loads(meta).get(\"caption\", \"(processing)\")}') for start, end, meta in c.fetchall() if meta]; conn.close()"
pause
goto menu

:embeddings
echo.
echo === Embedding Statistics ===
python -c "import sqlite3; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT modality, COUNT(*) FROM embeddings GROUP BY modality'); print('\nEmbeddings by type:\n'); [print(f'  {mod}: {cnt}') for mod, cnt in c.fetchall()]; c.execute('SELECT COUNT(DISTINCT scene_id) FROM embeddings WHERE scene_id IS NOT NULL'); print(f'\nScenes with embeddings: {c.fetchone()[0]}'); conn.close()"
pause
goto menu

:knowledge_graph
echo.
echo === Knowledge Graph ===
python -c "import sqlite3; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT COUNT(*) FROM links'); print(f'\nTotal links: {c.fetchone()[0]}'); c.execute('SELECT relation, COUNT(*) FROM links GROUP BY relation'); print('\nLink types:'); [print(f'  {rel}: {cnt}') for rel, cnt in c.fetchall()]; conn.close()"
pause
goto menu

:export_scenes
echo.
echo === Exporting Scene List ===
python -c "import sqlite3, json; conn = sqlite3.connect('L:/goodq4all/data/memory.db'); c = conn.cursor(); c.execute('SELECT id, start, end, meta FROM scenes ORDER BY start'); scenes = [{'id': id, 'start': start, 'end': end, 'meta': json.loads(meta) if meta else {}} for id, start, end, meta in c.fetchall()]; output_path = 'L:/goodq4all/data/scene_export.json'; json.dump(scenes, open(output_path, 'w'), indent=2); print(f'\nExported {len(scenes)} scenes to: {output_path}'); conn.close()"
echo.
echo Opening export file...
notepad L:\goodq4all\data\scene_export.json
pause
goto menu

:end
echo.
echo Mission complete!
echo.
pause
