from app import create_app, init_web
app = create_app()
init_web(app)

if __name__ == '__main__':
    print("----------")
    app.run(
        host=app.config.get('SERVER_HOST', '0.0.0.0'),
        port=app.config.get('SERVER_PORT', 7070),
        # debug=app.config.get('DEBUG', True)
    )
