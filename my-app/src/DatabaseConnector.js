// src/DatabaseConnector.js
import React, { useState } from 'react';

const DatabaseConnector = () => {
    const [server, setServer] = useState('');
    const [database, setDatabase] = useState('');
    const [message, setMessage] = useState('');

    const handleSubmit = async (e) => {
        e.preventDefault();
        try {
            const response = await fetch('http://localhost:5000/api/connect', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ server, database }),
            });

            const data = await response.json();
            if (response.ok) {
                setMessage(data.message);
            } else {
                setMessage(`Error: ${data.error}`);
            }
        } catch (error) {
            setMessage(`Error: ${error.message}`);
        }
    };

    return (
        <div>
            <h2>Connect to Database</h2>
            <form onSubmit={handleSubmit}>
                <div>
                    <label>
                        Server Name:
                        <input
                            type="text"
                            value={server}
                            onChange={(e) => setServer(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <div>
                    <label>
                        Database Name:
                        <input
                            type="text"
                            value={database}
                            onChange={(e) => setDatabase(e.target.value)}
                            required
                        />
                    </label>
                </div>
                <button type="submit">Connect</button>
            </form>
            {message && <p>{message}</p>}
        </div>
    );
};

export default DatabaseConnector;