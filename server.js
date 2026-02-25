const express = require('express');
const nodemailer = require('nodemailer');
const path = require('path');
const cors = require('cors');
require('dotenv').config();

const app = express();
const port = process.env.PORT || 3000;

app.set('trust proxy', 1);

const allowedOrigins = (process.env.ALLOWED_ORIGINS ||
    'https://testauto.no,https://www.testauto.no,http://localhost:3000')
    .split(',')
    .map((origin) => origin.trim())
    .filter(Boolean);

app.use(cors({
    origin: (origin, callback) => {
        if (!origin || allowedOrigins.includes(origin)) {
            return callback(null, true);
        }
        return callback(new Error('Origin is not allowed by CORS'));
    },
    methods: ['GET', 'POST'],
    optionsSuccessStatus: 204
}));

app.use((req, res, next) => {
    res.setHeader('X-Content-Type-Options', 'nosniff');
    res.setHeader('X-Frame-Options', 'DENY');
    res.setHeader('Referrer-Policy', 'strict-origin-when-cross-origin');
    res.setHeader('Permissions-Policy', 'camera=(), microphone=(), geolocation=()');
    next();
});

app.use(express.urlencoded({ extended: true, limit: '20kb' }));
app.use(express.json({ limit: '20kb' }));

app.use(express.static(__dirname));

const transporter = nodemailer.createTransport({
    service: 'gmail',
    auth: {
        user: process.env.SENDER_EMAIL,
        pass: process.env.SENDER_PASSWORD
    }
});

const RATE_LIMIT_WINDOW_MS = 10 * 60 * 1000;
const RATE_LIMIT_MAX_REQUESTS = 10;
const requestCounters = new Map();

function getClientIp(req) {
    return req.ip || req.connection?.remoteAddress || 'unknown';
}

function isRateLimited(ip) {
    const now = Date.now();

    if (requestCounters.size > 5000) {
        for (const [key, value] of requestCounters.entries()) {
            if (now - value.windowStart > RATE_LIMIT_WINDOW_MS) {
                requestCounters.delete(key);
            }
        }
    }

    const current = requestCounters.get(ip);

    if (!current || now - current.windowStart > RATE_LIMIT_WINDOW_MS) {
        requestCounters.set(ip, { count: 1, windowStart: now });
        return false;
    }

    current.count += 1;
    requestCounters.set(ip, current);
    return current.count > RATE_LIMIT_MAX_REQUESTS;
}

function sanitizeInput(value, maxLength) {
    if (typeof value !== 'string') {
        return '';
    }
    return value.trim().slice(0, maxLength);
}

app.get('/', (req, res) => {
    res.sendFile(path.join(__dirname, 'index.html'));
});

app.post('/send-email', async (req, res) => {
    const ip = getClientIp(req);
    if (isRateLimited(ip)) {
        return res.status(429).send('Too many requests. Please try again later.');
    }

    const name = sanitizeInput(req.body.name, 120);
    const email = sanitizeInput(req.body.email, 254);
    const message = sanitizeInput(req.body.message, 4000);
    const website = sanitizeInput(req.body.website, 200);
    const formStartedAt = Number(req.body.formStartedAt);

    if (website) {
        return res.status(400).send('Invalid form submission.');
    }

    const submittedTooFast = Number.isFinite(formStartedAt) && (Date.now() - formStartedAt) < 3000;
    if (!Number.isFinite(formStartedAt) || submittedTooFast) {
        return res.status(400).send('Invalid form submission.');
    }

    const emailPattern = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
    if (!name || !emailPattern.test(email) || message.length < 10) {
        return res.status(400).send('Please provide valid contact details and a message.');
    }

    const mailOptions = {
        from: process.env.SENDER_EMAIL,
        to: process.env.RECEIVER_EMAIL,
        subject: `Contact form submission from ${name}`,
        text: `Name: ${name}\nEmail: ${email}\nIP: ${ip}\n\nMessage:\n${message}`
    };

    try {
        await transporter.sendMail(mailOptions);
        return res.send('Email sent successfully.');
    } catch (error) {
        return res.status(500).send('Unable to send message right now. Please try again later.');
    }
});

app.use((error, req, res, next) => {
    if (error && typeof error.message === 'string' && error.message.includes('CORS')) {
        return res.status(403).send('Request origin is not allowed.');
    }
    return res.status(500).send('Unexpected server error.');
});

app.listen(port, () => {
    console.log(`Server is running on http://localhost:${port}`);
});
