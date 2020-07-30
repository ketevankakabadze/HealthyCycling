<<<<<<< HEAD
mkdir -p ~/.streamlit/

echo "[server]
headless = true
enableCORS=false
port = $PORT
=======
mkdir -p ~/.streamlit

echo "[server]
headless = true
port = $PORT
enableCORS = false
>>>>>>> f767319042589b8df60a02327e164d56c3ab5a08
" > ~/.streamlit/config.toml