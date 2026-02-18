import { useEffect } from 'react';

function LiveChart({ symbol }) {
  useEffect(() => {
    const container = document.getElementById('tv_chart');
    if (!container) return;

    container.innerHTML = '';

    const script = document.createElement('script');
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js';
    script.async = true;

    script.innerHTML = JSON.stringify({
      autosize: true,
      symbol: symbol,
      interval: '5',
      timezone: 'Asia/Kolkata',
      theme: 'dark',
      style: '1',
      locale: 'en',
      enable_publishing: false,
      hide_top_toolbar: false,
      hide_legend: false,
      save_image: false,
      studies: ['RSI@tv-basicstudies', 'MACD@tv-basicstudies']
    });

    container.appendChild(script);
  }, [symbol]);

  return <div id="tv_chart" style={{ width: '100%', height: '100%' }} />;
}

export default LiveChart;
