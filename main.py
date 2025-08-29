from dotenv import load_dotenv
load_dotenv()

import threading
from app import create_app
from db.query_runners.query_runner import run_query_runner
from app.utils.generalMethods import ins_configuration
from app.utils.global_config import env_mode
app = create_app('NUBOT')

if __name__ == '__main__':
    thread_query_runner = threading.Thread(target=run_query_runner)
    thread_query_runner.start()
    app.run(host='0.0.0.0', port=int(ins_configuration.get(env_mode,'nubot_main')), debug=True)