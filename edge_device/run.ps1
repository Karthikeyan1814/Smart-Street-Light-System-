# Set env vars and run the edge device. Edit values for your network.
$env:CENTRAL_SERVER_HOST = if ($env:CENTRAL_SERVER_HOST) { $env:CENTRAL_SERVER_HOST } else { "192.168.X.X" }
$env:CENTRAL_SERVER_PORT = if ($env:CENTRAL_SERVER_PORT) { $env:CENTRAL_SERVER_PORT } else { "5000" }
$env:API_KEY = if ($env:API_KEY) { $env:API_KEY } else { "dev-edge-api-key-change-me" }
$env:RUN_ON_RPI = if ($env:RUN_ON_RPI) { $env:RUN_ON_RPI } else { "true" }
$env:TOWER_ID = if ($env:TOWER_ID) { $env:TOWER_ID } else { "TOWER_01" }
$env:LOCATION = if ($env:LOCATION) { $env:LOCATION } else { "Main_Street" }
& python edge_main.py @args
