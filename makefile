compile:
	python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/guiche_info.proto
	python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/terminal.proto
	python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/backup.proto
	python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/client.proto
	python3 -m grpc_tools.protoc -I protos --python_out=. --grpc_python_out=. protos/heartbeat.proto
