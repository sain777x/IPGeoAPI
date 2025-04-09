from flask import Flask, request, jsonify
import requests
import json
import time

app = Flask(__name__)
app.config['JSON_AS_ASCII'] = False  # Tenta evitar escape de Unicode

# Função para obter coordenadas do IP via ip-api.com
def get_coordinates_from_ip(ip):
    try:
        response = requests.get(f"http://ip-api.com/json/{ip}")
        data = response.json()
        if data["status"] == "success":
            return data["lat"], data["lon"]
        raise Exception(f"Falha ao obter coordenadas do IP: {data.get('message', 'Erro desconhecido')}")
    except requests.exceptions.SSLError as e:
        raise Exception(f"Erro SSL ao conectar ao ip-api.com: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro na requisição ao ip-api.com: {str(e)}")

# Fallback 1: Nominatim (OpenStreetMap)
def get_nominatim_fallback(lat, lon):
    url = f"https://nominatim.openstreetmap.org/reverse?lat={lat}&lon={lon}&format=json&addressdetails=1"
    headers = {"User-Agent": "IPGeoApp/1.0 (matheus@example.com)"}  # Substitua por seu e-mail
    try:
        response = requests.get(url, headers=headers)
        print("Status HTTP do Nominatim:", response.status_code)
        print("Resposta bruta do Nominatim (texto):", response.text)
        data = response.json()
        addr = data.get("address", {})
        cep = addr.get("postcode", "")
        if cep:
            return cep
        return ""
    except requests.exceptions.SSLError as e:
        print(f"Erro SSL ao conectar ao Nominatim: {str(e)}")
        return ""
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição ao Nominatim: {str(e)}")
        return ""

# Fallback 2: Geoapify Reverse Geocoding API
def get_geoapify_fallback(lat, lon):
    api_key = "bba5b60ad1ef4d939c13bdfe77404a2c"  # Sua chave Geoapify
    url = f"https://api.geoapify.com/v1/geocode/reverse?lat={lat}&lon={lon}&apiKey={api_key}"
    try:
        response = requests.get(url)
        print("Status HTTP da Geoapify:", response.status_code)
        print("Resposta bruta da Geoapify (texto):", response.text)
        data = response.json()
        if not data.get("features"):
            return ""
        addr = data["features"][0]["properties"]
        cep = addr.get("postcode", "")
        if cep:
            return cep
        return ""
    except requests.exceptions.SSLError as e:
        print(f"Erro SSL ao conectar à Geoapify: {str(e)}")
        return ""
    except requests.exceptions.RequestException as e:
        print(f"Erro na requisição à Geoapify: {str(e)}")
        return ""

# Função principal para obter endereço com múltiplos fallbacks
def get_nearest_address(lat, lon):
    api_key = "c5ebAEMvUgmDGA7feF7ADFfrCwac63N9"  # Sua chave da TomTom
    url = f"https://api.tomtom.com/search/2/reverseGeocode/{lat},{lon}.json?key={api_key}"
    try:
        response = requests.get(url)
        print("Status HTTP da TomTom:", response.status_code)
        print("Resposta bruta da TomTom (texto):", response.text)
        
        if response.status_code != 200:
            raise Exception(f"Erro HTTP {response.status_code}: {response.text}")
        
        data = response.json()
        if not data.get("addresses"):
            raise Exception("Nenhum endereço encontrado para as coordenadas fornecidas")
        
        addr = data["addresses"][0]["address"]
        street = addr.get("streetName", "")
        house_number = addr.get("streetNumber", "")
        street_address = f"{street}, {house_number}" if house_number else street
        
        address_data = {
            "Country": addr.get("country", ""),
            "Street Address": street_address,
            "City": addr.get("municipality", ""),
            "State/Province": addr.get("countrySubdivisionName", ""),
            "Código Postal": addr.get("extendedPostalCode", "")
        }
        
        # Se o CEP estiver ausente, tenta os fallbacks na ordem
        if not address_data["Código Postal"]:
            print("CEP ausente na TomTom, buscando no Nominatim...")
            time.sleep(1)  # Respeita o limite do Nominatim
            address_data["Código Postal"] = get_nominatim_fallback(lat, lon)
        
        if not address_data["Código Postal"]:
            print("CEP ausente no Nominatim, buscando na Geoapify...")
            address_data["Código Postal"] = get_geoapify_fallback(lat, lon)
        
        # Mantém todos os campos como obrigatórios
        required_fields = ["Country", "Street Address", "City", "State/Province", "Código Postal"]
        missing_fields = [field for field in required_fields if not address_data[field]]
        if missing_fields:
            raise Exception(f"Campos obrigatórios ausentes: {', '.join(missing_fields)}")
        
        return address_data
    except requests.exceptions.SSLError as e:
        raise Exception(f"Erro SSL ao conectar à TomTom: {str(e)}")
    except requests.exceptions.RequestException as e:
        raise Exception(f"Erro na requisição à TomTom: {str(e)}")
    except ValueError as e:
        raise Exception(f"Erro ao parsear JSON da TomTom: {str(e)} - Resposta: {response.text}")

@app.route("/nearest-address", methods=["GET"])
def nearest_address():
    ip = request.args.get("ip")
    if not ip:
        return app.response_class(
            response=json.dumps({"error": "IP é necessário"}, ensure_ascii=False),
            status=400,
            mimetype='application/json'
        )
    
    try:
        lat, lon = get_coordinates_from_ip(ip)
        address = get_nearest_address(lat, lon)
        response_data = {
            "ip": ip,
            "coordinates": {"latitude": lat, "longitude": lon},
            "address": address
        }
        return app.response_class(
            response=json.dumps(response_data, ensure_ascii=False),
            status=200,
            mimetype='application/json'
        )
    except Exception as e:
        response_data = {
            "ip": ip,
            "coordinates": {"latitude": lat if 'lat' in locals() else None, "longitude": lon if 'lon' in locals() else None},
            "error": str(e)
        }
        return app.response_class(
            response=json.dumps(response_data, ensure_ascii=False),
            status=500,
            mimetype='application/json'
        )

if __name__ == "__main__":
    app.run(debug=True, port=5001)  # Porta 5001