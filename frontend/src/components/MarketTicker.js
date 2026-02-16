import { useEffect } from 'react';

function MarketTicker() {
  useEffect(() => {
    const container = document.getElementById('ticker');

    container.innerHTML = '';

    const script = document.createElement('script');
    script.src =
      'https://s3.tradingview.com/external-embedding/embed-widget-ticker-tape.js';
    script.async = true;

    script.innerHTML = JSON.stringify({
      symbols: [
        { proName: 'NSE:NIFTY50', title: 'NIFTY 50' },
        { proName: 'NSE:BANKNIFTY1!', title: 'BANK NIFTY' },
        { proName: 'BSE:SENSEX', title: 'SENSEX' }
      ],
      showSymbolLogo: true,
      isTransparent: false,
      displayMode: 'adaptive',
      colorTheme: 'dark',
      locale: 'en'
    });

    container.appendChild(script);
  }, []);

  return <div id="ticker"></div>;
}

export default MarketTicker;
