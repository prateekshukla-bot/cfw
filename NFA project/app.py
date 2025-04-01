from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index2.html')  # This will render index.html from the 'templates' folder

if __name__ == '__main__':
    app.run(host='0.0.0.0',debug=True)