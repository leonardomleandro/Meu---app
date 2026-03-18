import os
import json
import webbrowser
import csv
from datetime import datetime, timedelta
from decimal import Decimal, getcontext
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.textinput import TextInput
from kivy.uix.scrollview import ScrollView
from kivy.uix.spinner import Spinner
from kivy.uix.tabbedpanel import TabbedPanel, TabbedPanelItem
from kivy.core.window import Window
from kivy.uix.gridlayout import GridLayout

getcontext().prec = 28
Window.clearcolor = (0.95, 0.95, 0.95, 1)

class Produto:
    def __init__(self, nome, preco, lucro, estoque):
        self.nome = nome
        self.preco = Decimal(str(preco))
        self.lucro_un = Decimal(str(lucro))
        self.estoque = estoque

class YakultMestrePro(App):
    def build(self):
        self.arquivo_vendas = "vendas_yakult_mestre.csv"
        self.arquivo_estoque = "estoque_yakult.json"
        self.cesta = []
        self.dias_map = {"Segunda": 0, "Terça": 1, "Quarta": 2, "Quinta": 3, "Sexta": 4}
        
        self.lista_produtos = [
            Produto('YAKULT TRAD.', 1.65, 0.3427, 0),
            Produto('YAKULT PÊSSEGO', 1.65, 0.3427, 0),
            Produto('YAKULT 40', 2.05, 0.4755, 0),
            Produto('YAKULT 40 LIGHT', 2.10, 0.4873, 0),
            Produto('SOFYL', 2.60, 0.5405, 0),
            Produto('TAFFMAN EX', 4.50, 0.9354, 0),
            Produto('HILINE F', 4.50, 0.9354, 0),
            Produto('SUCO DE MAÇÃ', 3.50, 0.6932, 0),
            Produto('TONYU', 3.50, 0.6932, 0),
            Produto('YODEL', 3.50, 0.7451, 0)
        ]
        
        self.carregar_estoque_real()
        self.verificar_csv()

        root = BoxLayout(orientation='vertical')
        
        # --- TOPO FINANCEIRO (AGORA DINÂMICO POR ABA) ---
        self.painel_topo = BoxLayout(orientation='vertical', size_hint_y=None, height=120, padding=10)
        with self.painel_topo.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.1, 0.1, 0.1, 1)
            self.rect = Rectangle(size=self.painel_topo.size, pos=self.painel_topo.pos)
        self.painel_topo.bind(size=self._update_rect, pos=self._update_rect)

        linha_val = BoxLayout(spacing=5)
        self.lbl_din = Label(text="DIN: R$0.00", font_size='12sp')
        self.lbl_pix = Label(text="PIX: R$0.00", font_size='12sp', color=(0.4, 0.8, 1, 1))
        self.lbl_fia = Label(text="FIA: R$0.00", font_size='12sp', color=(1, 0.4, 0.4, 1))
        linha_val.add_widget(self.lbl_din); linha_val.add_widget(self.lbl_pix); linha_val.add_widget(self.lbl_fia)
        self.lbl_lucro_total = Label(text="LUCRO DO DIA: R$ 0.00", bold=True, font_size='22sp', color=(0.2, 1, 0.2, 1))
        self.painel_topo.add_widget(linha_val); self.painel_topo.add_widget(self.lbl_lucro_total)
        root.add_widget(self.painel_topo)

        # --- ABAS ---
        self.tp = TabbedPanel(do_default_tab=False)
        self.inputs = {}
        
        for dia in ["Segunda", "Terça", "Quarta", "Quinta", "Sexta"]:
            tab = TabbedPanelItem(text=dia)
            self.setup_vendas_ui(tab, dia)
            self.tp.add_widget(tab)
        
        self.tab_est = TabbedPanelItem(text="Estoque"); self.setup_estoque_ui(self.tab_est); self.tp.add_widget(self.tab_est)
        self.tab_rel = TabbedPanelItem(text="Relatórios"); self.setup_relatorios_ui(self.tab_rel); self.tp.add_widget(self.tab_rel)
        
        self.tp.bind(current_tab=self.on_tab_change)
        root.add_widget(self.tp)

        # --- RODAPÉ FORNECEDOR ---
        rodape = BoxLayout(orientation='horizontal', size_hint_y=None, height=60, padding=5, spacing=5)
        with rodape.canvas.before:
            from kivy.graphics import Color, Rectangle
            Color(0.2, 0.2, 0.2, 1)
            self.rect_rod = Rectangle(size=rodape.size, pos=rodape.pos)
        rodape.bind(size=self._update_rect_rod, pos=self._update_rect_rod)
        self.txt_forn_val = TextInput(hint_text="R$ VALOR", input_filter='float', multiline=False, size_hint_x=0.3)
        btn_forn_pix = Button(text="FORN PIX", background_color=(0, 0.5, 0.8, 1))
        btn_forn_bol = Button(text="FORN BOLETO", background_color=(0.6, 0.4, 0, 1))
        btn_forn_pix.bind(on_press=lambda x: self.pagar_fornecedor("PIX"))
        btn_forn_bol.bind(on_press=lambda x: self.pagar_fornecedor("BOLETO"))
        rodape.add_widget(self.txt_forn_val); rodape.add_widget(btn_forn_pix); rodape.add_widget(btn_forn_bol)
        root.add_widget(rodape)

        self.atualizar_tudo(); return root

    def on_tab_change(self, instance, value):
        for tab in self.tp.tab_list:
            tab.color = (1, 1, 1, 1)
            tab.bold = False
        value.color = (1, 0, 0, 1) 
        value.bold = True
        self.atualizar_tudo()

    def get_data_do_dia_semana(self, nome_dia):
        hoje = datetime.now()
        if nome_dia in self.dias_map:
            margem = self.dias_map[nome_dia] - hoje.weekday()
            return (hoje + timedelta(days=margem)).strftime("%d/%m/%Y")
        return hoje.strftime("%d/%m/%Y")

    def atualizar_lucro_realtime(self):
        # Pega a data da aba que você está clicando agora
        aba_ativa = self.tp.current_tab.text
        if aba_ativa not in self.dias_map:
            return
            
        data_alvo = self.get_data_do_dia_semana(aba_ativa)
        sd, sp, sf, lt = Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')
        
        if os.path.exists(self.arquivo_vendas):
            with open(self.arquivo_vendas, "r", encoding="utf-8") as f:
                r = csv.reader(f, delimiter=';')
                next(r, None)
                for d in r:
                    if d[0] == data_alvo: # Só soma se for o dia da aba aberta
                        lt += Decimal(d[6])
                        if "FORNECEDOR" not in d[1]:
                            if d[5] == 'DINHEIRO': sd += Decimal(d[4])
                            elif d[5] == 'PIX': sp += Decimal(d[4])
                            elif d[5] == 'FIADO': sf += Decimal(d[4])
        
        self.lbl_din.text = f"DIN: R${sd:.2f}"
        self.lbl_pix.text = f"PIX: R${sp:.2f}"
        self.lbl_fia.text = f"FIA: R${sf:.2f}"
        self.lbl_lucro_total.text = f"LUCRO {aba_ativa.upper()}: R$ {lt:.2f}"

    def finalizar_venda(self, dia_nome):
        d = self.inputs[dia_nome]; nome = d['cli'].text.upper().strip()
        if not self.cesta or not nome: return
        data_venda = self.get_data_do_dia_semana(dia_nome)
        with open(self.arquivo_vendas, "a", encoding="utf-8") as f:
            for item in self.cesta:
                p_obj = next(p for p in self.lista_produtos if p.nome == item['prod'])
                val_t = p_obj.preco * Decimal(str(item['qtd'])); luc_t = p_obj.lucro_un * Decimal(str(item['qtd']))
                p_obj.estoque -= item['qtd']
                f.write(f"{data_venda};{nome};{p_obj.nome};{item['qtd']};{val_t:.2f};{d['pg'].text};{luc_t:.4f}\n")
        self.salvar_estoque_real(); self.cesta = []; d['cli'].text = ""; d['lbl'].text = "✅ SALVO!"; self.atualizar_tudo()

    def atualizar_historico_tela(self):
        aba_atual = self.tp.current_tab.text
        if aba_atual not in self.inputs: return
        grid = self.inputs[aba_atual]['grid']; grid.clear_widgets()
        data_alvo = self.get_data_do_dia_semana(aba_atual)
        if os.path.exists(self.arquivo_vendas):
            with open(self.arquivo_vendas, "r", encoding="utf-8") as f:
                todas = list(csv.reader(f, delimiter=';'))
                for i, v in enumerate(todas[1:]):
                    if v[0] == data_alvo:
                        r = BoxLayout(size_hint_y=None, height=50, spacing=5)
                        # Mostra: Nome | Valor | Metodo
                        r.add_widget(Label(text=f"{v[1]} | R${v[4]} | {v[5]}", color=(0,0,0,1), size_hint_x=0.8, font_size='11sp'))
                        btn = Button(text="❌", size_hint_x=0.2, background_color=(0.9, 0.2, 0.2, 1))
                        btn.bind(on_press=lambda x, idx=i+1: self.apagar_venda(idx))
                        r.add_widget(btn); grid.add_widget(r, index=len(grid.children))

    # --- RESTANTE DAS FUNÇÕES (ESTOQUE, SETUP, ETC) ---
    def setup_vendas_ui(self, tab, dia):
        lay = BoxLayout(orientation='vertical', padding=8, spacing=8)
        txt_cli = TextInput(hint_text="NOME CLIENTE", size_hint_y=None, height=50, multiline=False)
        row_p = BoxLayout(size_hint_y=None, height=50, spacing=5)
        spn_p = Spinner(text='PRODUTOS', values=[p.nome for p in self.lista_produtos], size_hint_x=0.6)
        txt_q = TextInput(hint_text="QTD", input_filter='int', size_hint_x=0.2)
        btn_add = Button(text="ADD", size_hint_x=0.2, background_color=(0, 0.7, 0.4, 1), bold=True)
        row_p.add_widget(spn_p); row_p.add_widget(txt_q); row_p.add_widget(btn_add)
        lbl_c = Label(text="Cesta: 0 itens", color=(0,0,0,1), size_hint_y=None, height=30)
        spn_pg = Spinner(text='DINHEIRO', values=('DINHEIRO', 'PIX', 'FIADO'), size_hint_y=None, height=50)
        ghist = GridLayout(cols=1, spacing=3, size_hint_y=None); ghist.bind(minimum_height=ghist.setter('height'))
        self.inputs[dia] = {'cli': txt_cli, 'prod': spn_p, 'qtd': txt_q, 'lbl': lbl_c, 'pg': spn_pg, 'grid': ghist}
        btn_add.bind(on_press=lambda x: self.add_cesta(dia))
        btn_fin = Button(text="FINALIZAR COMPRA", background_color=(0.1, 0.4, 0.9, 1), size_hint_y=None, height=65, bold=True)
        btn_fin.bind(on_press=lambda x: self.finalizar_venda(dia))
        scr = ScrollView(); scr.add_widget(ghist)
        lay.add_widget(txt_cli); lay.add_widget(row_p); lay.add_widget(lbl_c); lay.add_widget(spn_pg); lay.add_widget(btn_fin); lay.add_widget(scr); tab.add_widget(lay)

    def setup_estoque_ui(self, tab):
        lay = BoxLayout(orientation='vertical', padding=10, spacing=8)
        self.spn_e = Spinner(text='PRODUTO', values=[p.nome for p in self.lista_produtos], size_hint_y=None, height=50)
        self.txt_qe = TextInput(hint_text="QTD", input_filter='int', size_hint_y=None, height=50)
        btn_add_est = Button(text="➕ ADICIONAR AO ESTOQUE", background_color=(0, 0.6, 0.3, 1), size_hint_y=None, height=55, bold=True)
        btn_add_est.bind(on_press=lambda x: self.aj_est())
        self.grid_est = GridLayout(cols=1, spacing=2, size_hint_y=None); self.grid_est.bind(minimum_height=self.grid_est.setter('height'))
        scr = ScrollView(); scr.add_widget(self.grid_est)
        btn_zerar = Button(text="⚠️ ZERAR TODO ESTOQUE", background_color=(0.8, 0, 0, 1), size_hint_y=None, height=50)
        btn_zerar.bind(on_press=self.zerar_estoque_total)
        lay.add_widget(self.spn_e); lay.add_widget(self.txt_qe); lay.add_widget(btn_add_est); lay.add_widget(scr); lay.add_widget(btn_zerar)
        tab.add_widget(lay)

    def setup_relatorios_ui(self, tab):
        lay = BoxLayout(orientation='vertical', padding=20, spacing=15)
        btn_wa = Button(text="📱 WHATSAPP", background_color=(0.07, 0.4, 0.2, 1), size_hint_y=None, height=70, bold=True)
        btn_wa.bind(on_press=self.gerar_whatsapp)
        btn_ex = Button(text="📊 EXCEL", background_color=(0.1, 0.3, 0.6, 1), size_hint_y=None, height=70)
        btn_ex.bind(on_press=lambda x: webbrowser.open(self.arquivo_vendas))
        lay.add_widget(btn_wa); lay.add_widget(btn_ex); tab.add_widget(lay)

    def pagar_fornecedor(self, tipo):
        val = self.txt_forn_val.text.strip()
        if not val: return
        hoje = datetime.now().strftime("%d/%m/%Y")
        valor_neg = Decimal(val) * -1
        with open(self.arquivo_vendas, "a", encoding="utf-8") as f: f.write(f"{hoje};PAGAMENTO FORNECEDOR {tipo};-;-;{valor_neg:.2f};{tipo};{valor_neg:.2f}\n")
        self.txt_forn_val.text = ""; self.atualizar_tudo()

    def aj_est(self):
        if self.spn_e.text != 'PRODUTO' and self.txt_qe.text:
            p = next(p for p in self.lista_produtos if p.nome == self.spn_e.text); p.estoque += int(self.txt_qe.text)
            self.salvar_estoque_real(); self.atualizar_estoque_lista(); self.txt_qe.text = ""
    def zerar_estoque_total(self, instance):
        for p in self.lista_produtos: p.estoque = 0
        self.salvar_estoque_real(); self.atualizar_estoque_lista()
    def atualizar_estoque_lista(self):
        if hasattr(self, 'grid_est'):
            self.grid_est.clear_widgets()
            for p in sorted(self.lista_produtos, key=lambda x: x.nome):
                self.grid_est.add_widget(Label(text=f"{p.nome}: {p.estoque} un.", color=(0,0,0,1), size_hint_y=None, height=35))
    def apagar_venda(self, idx):
        if not os.path.exists(self.arquivo_vendas): return
        with open(self.arquivo_vendas, "r", encoding="utf-8") as f: ls = list(csv.reader(f, delimiter=';'))
        if 0 < idx < len(ls):
            v = ls[idx]; p = next((p for p in self.lista_produtos if p.nome == v[2]), None)
            if p: p.estoque += int(v[3])
            ls.pop(idx)
            with open(self.arquivo_vendas, "w", encoding="utf-8", newline='') as f: csv.writer(f, delimiter=';').writerows(ls)
            self.salvar_estoque_real(); self.atualizar_tudo()
    def carregar_estoque_real(self):
        if os.path.exists(self.arquivo_estoque):
            with open(self.arquivo_estoque, 'r') as f:
                d = json.load(f); [setattr(p, 'estoque', d.get(p.nome, 0)) for p in self.lista_produtos]
    def salvar_estoque_real(self):
        with open(self.arquivo_estoque, 'w') as f: json.dump({p.nome: p.estoque for p in self.lista_produtos}, f)
    def add_cesta(self, dia):
        d = self.inputs[dia]
        if d['prod'].text != 'PRODUTOS' and d['qtd'].text:
            self.cesta.append({'prod': d['prod'].text, 'qtd': int(d['qtd'].text)}); d['lbl'].text = f"Cesta: {len(self.cesta)} itens"; d['qtd'].text = ""
    def atualizar_tudo(self): self.atualizar_historico_tela(); self.atualizar_estoque_lista(); self.atualizar_lucro_realtime()
    def verificar_csv(self):
        if not os.path.exists(self.arquivo_vendas):
            with open(self.arquivo_vendas, "w", encoding="utf-8") as f: f.write("Data;Cliente;Produto;Qtd;Valor;Pagamento;Lucro\n")
    def _update_rect(self, instance, value): self.rect.pos = instance.pos; self.rect.size = instance.size
    def _update_rect_rod(self, instance, value): self.rect_rod.pos = instance.pos; self.rect_rod.size = instance.size
    def gerar_whatsapp(self, instance):
        aba_at = self.tp.current_tab.text; data_alvo = self.get_data_do_dia_semana(aba_at)
        rel, fia, saidas, sd, sp, sf, lt = "", "", "", Decimal('0'), Decimal('0'), Decimal('0'), Decimal('0')
        if os.path.exists(self.arquivo_vendas):
            with open(self.arquivo_vendas, "r", encoding="utf-8") as f:
                r = csv.reader(f, delimiter=';'); next(r)
                for d in r:
                    if d[0] == data_alvo:
                        if "FORNECEDOR" in d[1]: saidas += f"💸 {d[1]}: R${d[4]}%0A"; lt += Decimal(d[6])
                        else:
                            lt += Decimal(d[6]); rel += f"• {d[1]}: {d[2]} (x{d[3]}) - R${d[4]}%0A"
                            if d[5] == 'DINHEIRO': sd += Decimal(d[4])
                            elif d[5] == 'PIX': sp += Decimal(d[4])
                            elif d[5] == 'FIADO': sf += Decimal(d[4]); fia += f"⚠️ {d[1]}: R${d[4]}%0A"
        msg = f"*📊 RELATÓRIO {aba_at.upper()} ({data_alvo})*%0A%0A*👤 VENDAS:*%0A{rel}%0A*💳 SAÍDAS:*%0A{saidas}%0A*🔴 FIADOS:*%0A{fia}%0A*💰 RESUMO:*%0ADIN: R${sd:.2f} | PIX: R${sp:.2f} | FIA: R${sf:.2f}%0A*📈 LUCRO: R$ {lt:.2f}*"
        webbrowser.open(f"https://wa.me/?text={msg}")

if __name__ == '__main__':
    YakultMestrePro().run()
