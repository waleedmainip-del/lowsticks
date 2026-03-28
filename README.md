# lowsticks
enjoy the contact
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>My Game Portfolio</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background-color: #0f0f0f;
            color: #ffffff;
            margin: 0;
            padding: 0;
            scroll-behavior: smooth;
        }
        header {
            background: linear-gradient(45deg, #6200ea, #03dac6);
            padding: 60px 20px;
            text-align: center;
        }
        .container {
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
        }
        h2 {
            border-left: 5px solid #03dac6;
            padding-left: 15px;
            margin-bottom: 30px;
        }
        .game-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
            gap: 25px;
        }
        .game-card {
            background-color: #1e1e1e;
            border-radius: 12px;
            overflow: hidden;
            transition: 0.3s;
            border: 1px solid #333;
        }
        .game-card:hover {
            transform: translateY(-8px);
            border-color: #03dac6;
        }
        .game-img {
            width: 100%;
            height: 180px;
            background-color: #252525;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #555;
            font-weight: bold;
        }
        .game-info {
            padding: 20px;
        }
        .btn-group {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        .btn {
            flex: 1;
            text-align: center;
            padding: 10px;
            text-decoration: none;
            border-radius: 6px;
            font-weight: bold;
            font-size: 14px;
        }
        .btn-play { background-color: #03dac6; color: #000; }
        .btn-download { border: 1px solid #03dac6; color: #03dac6; }

        /* Contact Section */
        .contact-section {
            background-color: #161616;
            padding: 50px 20px;
            text-align: center;
            margin-top: 60px;
            border-top: 1px solid #333;
        }
        .contact-form {
            max-width: 500px;
            margin: 0 auto;
            text-align: left;
        }
        input, textarea {
            width: 100%;
            padding: 12px;
            margin: 10px 0;
            background: #252525;
            border: 1px solid #444;
            color: white;
            border-radius: 4px;
            box-sizing: border-box;
        }
        .submit-btn {
            background-color: #6200ea;
            color: white;
            border: none;
            padding: 15px;
            width: 100%;
            border-radius: 4px;
            cursor: pointer;
            font-weight: bold;
            transition: 0.3s;
        }
        .submit-btn:hover { background-color: #7c4dff; }
    </style>
</head>
<body>

<header>
    <h1>Waleed's Game Studio</h1>
    <p>Developing the future of interactive entertainment</p>
</header>

<div class="container">
    <h2>Featured Games</h2>
    <div class="game-grid">
        <div class="game-card">
            <div class="game-img">GAME SCREENSHOT HERE</div>
            <div class="game-info">
                <h3>Cyber Runner</h3>
                <p>An intense neon-soaked platformer. Can you beat the clock?</p>
                <div class="btn-group">
                    <a href="#" class="btn btn-play">Play Demo</a>
                    <a href="#" class="btn btn-download">Download</a>
                </div>
            </div>
        </div>

        <div class="game-card">
            <div class="game-img">GAME SCREENSHOT HERE</div>
            <div class="game-info">
                <h3>Tactical Arena</h3>
                <p>Strategic combat meets fast-paced decision making.</p>
                <div class="btn-group">
                    <a href="#" class="btn btn-play">Play Demo</a>
                    <a href="#" class="btn btn-download">Download</a>
                </div>
            </div>
        </div>
    </div>
</div>

<div class="contact-section">
    <h2>Get in Touch</h2>
    <p>Interested in collaborating or have a bug to report? Send a message!</p>
    <div class="contact-form">
        <form action="#" method="POST">
            <input type="text" placeholder="Your Name" required>
            <input type="email" placeholder="Your Email" required>
            <textarea rows="5" placeholder="Your Message" required></textarea>
            <button type="submit" class="submit-btn">Send Message</button>
        </form>
    </div>
</div>

</body>
</html>
