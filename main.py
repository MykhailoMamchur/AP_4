from flask import Flask

def create_app():
    app = Flask(__name__)

    @app.route('/api/v1/hello-world-4')
    def hello_world4():
        return "Hello World 4", 200
    
    return app

if __name__ == "__main__":
    app = create_app()
    app.run()
