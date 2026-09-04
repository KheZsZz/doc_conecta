import qrcode

def gerar_qr_code(link, nome_arquivo):
    # Configura os parâmetros visuais do QR Code
    qr = qrcode.QRCode(
        version=1,                                  # Controle de tamanho (1 a 40)
        error_correction=qrcode.constants.ERROR_CORRECT_L, # Nível de tolerância a danos
        box_size=10,                                # Tamanho de cada quadrado do código
        border=4,                                   # Espessura da margem branca
    )
    
    # Insere o link desejado
    qr.add_data(link)
    qr.make(fit=True)
    
    # Renderiza a imagem 
    imagem = qr.make_image(fill_color="black", back_color="white")
    
    # Salva no formato PNG
    imagem.save(nome_arquivo)
    print(f"QR Code gerado com sucesso: {nome_arquivo}")

# Exemplo de uso
url = "https://forms.gle/zRQLAbEJG37VkhdH8"
arquivo_saida = "meu_qrcode.png"

gerar_qr_code(url, arquivo_saida)