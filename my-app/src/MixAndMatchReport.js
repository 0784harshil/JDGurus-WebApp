// src/MixAndMatchReport.js
import React, { useEffect, useState } from 'react';

const MixAndMatchReport = () => {
    const [data, setData] = useState([]);
    const [error, setError] = useState(null);

    useEffect(() => {
        const fetchData = async () => {
            try {
                const response = await fetch('http://localhost:5000/mix-and-match');
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                const result = await response.json();
                setData(result);
            } catch (error) {
                setError(error.message);
            }
        };

        fetchData();
    }, []);

    if (error) {
        return <div>Error: {error}</div>;
    }

    return (
        <div>
            <h2>Mix and Match Report</h2>
            <table>
                <thead>
                    <tr>
                        <th>UPC</th>
                        <th>Item Name</th>
                        <th>Unit Price</th>
                        <th>Sale Price</th>
                        <th>Item Sold</th>
                        <th>Sale Amount</th>
                        <th>Mfg Deal</th>
                    </tr>
                </thead>
                <tbody>
                    {data.map((item, index) => (
                        <tr key={index}>
                            <td>{item.UPC}</td>
                            <td>{item['Item Name']}</td>
                            <td>{item['Unit Price']}</td>
                            <td>{item['Sale Price']}</td>
                            <td>{item['Item Sold']}</td>
                            <td>{item['Sale Amount']}</td>
                            <td>{item['Mfg.Deal']}</td>
                        </tr>
                    ))}
                </tbody>
            </table>
        </div>
    );
};

export default MixAndMatchReport;