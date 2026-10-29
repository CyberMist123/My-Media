# Stop only this project's containers (keeps volumes; never `down -v`).
docker compose -f 'D:\My Media\compose.yaml' -f 'D:\My Media\compose.stage-c.yaml' stop
