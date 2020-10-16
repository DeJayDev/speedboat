up:
	docker-compose up

down:
	docker-compose down

dbcli:
	docker-compose exec db /bin/bash

cli:
	docker-compose exec bot /bin/bash

worker-logs:
	docker-compose exec workers tail -F worker-0.log
