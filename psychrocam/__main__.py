# -*- coding: utf-8 -*-
if __name__ == "__main__":
    from psychrocam import app as application

    application.run(host="0.0.0.0", port=8000,
                    processes=1, threaded=True,
                    debug=application.config['DEBUG'])
