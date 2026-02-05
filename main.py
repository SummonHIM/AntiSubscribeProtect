from flask import Flask, jsonify, make_response

from board.base import load_boards

# Flask app
app = Flask(__name__)


BOARD_DIR = "board"
BOARDS = load_boards()


@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def catch_all(path: str):
    if path == "":
        # 根路径，返回 board 列表
        return jsonify({
            "boards": list(BOARDS.keys())
        })
    elif path.startswith("board/"):
        # 动态 board 路由
        name = path.split("/")[1]
        board = BOARDS.get(name)
        if board is None:
            return jsonify({
                "error": "board_not_found",
                "available": list(BOARDS.keys())
            }), 404

        # 调用 board.handle()
        return make_response(board.handle())
    else:
        # 404 fallback
        return jsonify({
            "error": "not_found",
            "available_boards": list(BOARDS.keys())
        }), 404


if __name__ == "__main__":
    app.run(port=8000, debug=True)
