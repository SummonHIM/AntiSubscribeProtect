import traceback

from flask import Flask, jsonify, make_response

from board.base import APIErrorException, load_boards

app = Flask(__name__)
BOARDS = load_boards()


@app.get("/", defaults={"path": ""})
@app.get("/<path:path>")
def catch_all(path: str):
    # 根目录
    if path == "":
        return jsonify({
            "code": 200,
            "boards": list(BOARDS.keys())
        })

    # 动态 board 路由
    elif path.startswith("board/"):
        name = path.split("/")[1]
        board = BOARDS.get(name)
        if board is None:
            return jsonify({
                "code": 404,
                "details": "Not Found",
                "boards": list(BOARDS.keys())
            }), 404

        # 调用 board.handle()
        try:
            return board.handle()
        except APIErrorException as e:
            return jsonify(e.to_dict()), e.code
        except Exception as e:
            traceback.print_exc()
            return jsonify({
                "code": 500,
                "details": "Internal Server Error",
            }), 500

    # 404
    else:
        return jsonify({
            "code": 404,
            "details": "Not Found",
            "boards": list(BOARDS.keys())
        }), 404


if __name__ == "__main__":
    app.run(port=8000, debug=True)
