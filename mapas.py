import html
import json

import folium
import pandas as pd
from branca.element import MacroElement
from folium.map import Layer
from folium.plugins import HeatMap
from jinja2 import Template

CENTRO_MAPA = [-30.0346, -51.2177]
ZOOM_MAPA = 12
LIMITES_LATITUDE = (-30.30, -29.90)
LIMITES_LONGITUDE = (-51.30, -51.00)

COR_GRAVE = "#d73027"
COR_DEMAIS = "#2b6cb0"

# Cor e formato de cada grupo de sinalização. Os dois juntos ajudam a
# diferenciar os grupos mesmo com muitos pontos sobrepostos.
ESTILO_SINALIZACAO = {
    "Travessia de pedestres": ("#2ca25f", "triangulo"),
    "Pare / retenção": ("#f28e2b", "octogono"),
    "Transporte coletivo": ("#7b3294", "quadrado"),
    "Velocidade e moderadores": ("#c9a400", "losango"),
    "Estacionamento": ("#17a2b8", "circulo"),
    "Divisão de pista e delimitação": ("#4d4d4d", "cruz"),
    "Bicicletas": ("#e377c2", "triangulo_invertido"),
    "Setas e orientação": ("#8c564b", "hexagono"),
    "Outras placas e marcações": ("#9e9e9e", "x"),
}


class CamadaPontos(Layer):
    """Camada Leaflet de pontos desenhados em canvas.

    Os pontos vão como uma lista compacta de [lat, lon, texto opcional] e os
    marcadores são criados no navegador, o que mantém o HTML pequeno mesmo com
    dezenas de milhares de pontos.
    """

    _template = Template("""
        {% macro script(this, kwargs) %}
        var {{ this.get_name() }} = L.layerGroup();
        (function () {
            var renderer = L.canvas({padding: 0.5});
            var pontos = {{ this.pontos }};
            var estilo = {{ this.estilo }};
            var marcadores = [];
            for (var i = 0; i < pontos.length; i++) {
                var p = pontos[i];
                var marcador = L.circleMarker(
                    [p[0], p[1]],
                    Object.assign({renderer: renderer}, estilo)
                );
                if (p.length > 2) { marcador.bindTooltip(p[2]); }
                marcador.addTo({{ this.get_name() }});
                marcadores.push(marcador);
            }

            // O raio cresce com o zoom: pequeno na cidade inteira (onde os
            // pontos se sobrepõem) e maior quando se aproxima do local.
            var mapa = {{ this._parent.get_name() }};
            var raioMin = {{ this.raio_min }}, raioMax = {{ this.raio_max }};
            function ajustarRaio() {
                var fracao = Math.min(1, Math.max(0, (mapa.getZoom() - 11) / 6));
                var raio = raioMin + (raioMax - raioMin) * fracao;
                for (var j = 0; j < marcadores.length; j++) {
                    marcadores[j].setRadius(raio);
                }
            }
            mapa.on("zoomend", ajustarRaio);
            ajustarRaio();
        })();
        {% if this.show %}
        {{ this.get_name() }}.addTo({{ this._parent.get_name() }});
        {% endif %}
        {% endmacro %}
    """)

    def __init__(self, pontos, estilo, name, raio_min, raio_max, show=True):
        super().__init__(name=name, overlay=True, control=True, show=show)
        self._name = "CamadaPontos"
        self.raio_min = raio_min
        self.raio_max = raio_max
        self.pontos = json.dumps(
            pontos,
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("</", "<\\/")
        self.estilo = json.dumps(estilo)


# O Leaflet só desenha círculos prontos. Para ter formatos diferentes e
# agrupar sinais por zoom, a sinalização é desenhada em um canvas próprio.
# Os pontos ficam em coordenadas de mundo (Mercator, de 0 a 1) e o agrupamento
# é feito em células de pixels do zoom atual, separadamente por grupo.
SCRIPT_SINALIZACAO = """
{% macro script(this, kwargs) %}
(function () {
    var mapa = {{ this._parent.get_name() }};
    var D = {{ this.dados }};
    var N = D.lat.length;
    var NC = D.cats.length;
    var TAMANHO_CELULA = 44;

    var wx = new Float64Array(N), wy = new Float64Array(N);
    var cat = new Int8Array(N);
    for (var i = 0; i < N; i++) {
        var lat = D.lat[i] * Math.PI / 180;
        wx[i] = (D.lon[i] + 180) / 360;
        wy[i] = (1 - Math.log(Math.tan(lat) + 1 / Math.cos(lat)) / Math.PI) / 2;
        cat[i] = D.cat[i];
    }
    var unitarios = new Uint32Array(N).fill(1);
    var individuais = { x: wx, y: wy, cat: cat, n: unitarios, ids: null };
    var visivel = [];
    for (var v = 0; v < NC; v++) { visivel.push(true); }
    var agrupar = true;
    var cache = {};

    // ---------- formatos ----------
    var CRUZ = [[-0.38,-1],[0.38,-1],[0.38,-0.38],[1,-0.38],[1,0.38],[0.38,0.38],
                [0.38,1],[-0.38,1],[-0.38,0.38],[-1,0.38],[-1,-0.38],[-0.38,-0.38]];
    var POLIGONOS = {
        triangulo: [[0,-1.25],[1.1,0.9],[-1.1,0.9]],
        triangulo_invertido: [[0,1.25],[1.1,-0.9],[-1.1,-0.9]],
        losango: [[0,-1.35],[1.35,0],[0,1.35],[-1.35,0]],
        cruz: CRUZ.map(function (p) { return [p[0] * 1.15, p[1] * 1.15]; }),
        x: CRUZ.map(function (p) {
            var c = Math.SQRT1_2;
            return [(p[0] - p[1]) * c * 1.15, (p[0] + p[1]) * c * 1.15];
        })
    };
    function regular(lados, rotacao) {
        var pts = [];
        for (var k = 0; k < lados; k++) {
            var a = rotacao + k * 2 * Math.PI / lados - Math.PI / 2;
            pts.push([Math.cos(a) * 1.15, Math.sin(a) * 1.15]);
        }
        return pts;
    }
    POLIGONOS.hexagono = regular(6, 0);
    POLIGONOS.octogono = regular(8, Math.PI / 8);

    function tracar(ctx, forma, x, y, r) {
        if (forma === "circulo") {
            ctx.moveTo(x + r, y);
            ctx.arc(x, y, r, 0, 6.283185307);
        } else if (forma === "quadrado") {
            ctx.rect(x - r * 0.9, y - r * 0.9, r * 1.8, r * 1.8);
        } else {
            var pts = POLIGONOS[forma];
            ctx.moveTo(x + pts[0][0] * r, y + pts[0][1] * r);
            for (var k = 1; k < pts.length; k++) {
                ctx.lineTo(x + pts[k][0] * r, y + pts[k][1] * r);
            }
            ctx.closePath();
        }
    }

    // ---------- agrupamento por zoom ----------
    function agrupamento(z) {
        if (cache[z]) { return cache[z]; }
        var escala = 256 * Math.pow(2, z);
        var chaves = new Map();
        var ids = new Int32Array(N);
        var gc = [], gn = [], gx = [], gy = [];
        for (var i = 0; i < N; i++) {
            var cx = Math.floor(wx[i] * escala / TAMANHO_CELULA);
            var cy = Math.floor(wy[i] * escala / TAMANHO_CELULA);
            var chave = (cat[i] * 4194304 + cx) * 4194304 + cy;
            var id = chaves.get(chave);
            if (id === undefined) {
                id = gn.length;
                chaves.set(chave, id);
                gc.push(cat[i]); gn.push(0); gx.push(0); gy.push(0);
            }
            ids[i] = id;
            gn[id] += 1; gx[id] += wx[i]; gy[id] += wy[i];
        }
        var M = gn.length;
        var x = new Float64Array(M), y = new Float64Array(M);
        for (var g = 0; g < M; g++) { x[g] = gx[g] / gn[g]; y[g] = gy[g] / gn[g]; }
        cache[z] = { x: x, y: y, cat: Int8Array.from(gc), n: Uint32Array.from(gn), ids: ids };
        return cache[z];
    }

    // ---------- canvas ----------
    // O canvas fica numa camada própria do Leaflet, abaixo da camada das
    // dicas (z-index 650), para a dica sempre aparecer por cima dos pontos.
    var camadaSinais = mapa.createPane("sinais");
    camadaSinais.style.zIndex = 450;
    camadaSinais.style.pointerEvents = "none";
    var canvas = document.createElement("canvas");
    canvas.style.cssText = "position:absolute;top:0;left:0;pointer-events:none;";
    camadaSinais.appendChild(canvas);
    // As camadas se movem junto com o mapa; o canvas acompanha o contrário,
    // para continuar cobrindo exatamente a área visível.
    function posicionar() {
        L.DomUtil.setPosition(canvas, mapa.containerPointToLayerPoint([0, 0]));
    }

    var fonteAtual = individuais;
    var hx = [], hy = [], hr = [], hk = [];
    var pendente = false;
    var zoomando = false;
    var desenhos = 0;
    window.sinaisDebug = function () {
        return { agrupar: agrupar, desenhados: hx.length, itens: fonteAtual.x.length,
                 total: N, zoom: mapa.getZoom(), desenhos: desenhos, zoomando: zoomando,
                 opacidade: canvas.style.opacity };
    };

    function rotulo(n) {
        return n < 1000 ? String(n) : (n / 1000).toFixed(1).replace(".", ",") + "k";
    }

    function desenhar() {
        pendente = false;
        desenhos += 1;
        posicionar();
        var tam = mapa.getSize();
        var dpr = window.devicePixelRatio || 1;
        var largura = Math.round(tam.x * dpr), altura = Math.round(tam.y * dpr);
        if (canvas.width !== largura || canvas.height !== altura) {
            canvas.width = largura; canvas.height = altura;
            canvas.style.width = tam.x + "px"; canvas.style.height = tam.y + "px";
        }
        var ctx = canvas.getContext("2d");
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, tam.x, tam.y);

        var zoom = mapa.getZoom();
        var fonte = agrupar ? agrupamento(Math.round(zoom)) : individuais;
        fonteAtual = fonte;
        var escala = 256 * Math.pow(2, zoom);
        var origem = mapa.getPixelBounds().min;
        var fracao = Math.min(1, Math.max(0, (zoom - 11) / 6));
        var base = 3 + 3.5 * fracao;
        var margem = 40;
        var total = fonte.x.length;

        // 1) itens visíveis na tela (tipo ligado e dentro da área do mapa),
        //    já separados por tipo
        var porTipo = [];
        for (var c0 = 0; c0 < NC; c0++) { porTipo.push([]); }
        var vx = new Float32Array(total), vy = new Float32Array(total), vr = new Float32Array(total);
        var nVis = 0;
        for (var k = 0; k < total; k++) {
            var ck = fonte.cat[k];
            if (!visivel[ck]) { continue; }
            var sx = fonte.x[k] * escala - origem.x;
            var sy = fonte.y[k] * escala - origem.y;
            if (sx < -margem || sy < -margem || sx > tam.x + margem || sy > tam.y + margem) { continue; }
            var n = fonte.n[k];
            vx[k] = sx; vy[k] = sy;
            vr[k] = n > 1 ? base + Math.min(10, 2.6 * Math.log2(n)) : base;
            porTipo[ck].push(k);
            nVis += 1;
        }

        // 2) desenho. Com poucos itens, um por um e dos maiores para os
        //    menores (os menores ficam por cima e continuam visíveis). Com
        //    muitos itens, um único traçado por tipo, que é bem mais rápido.
        hx = []; hy = []; hr = []; hk = [];
        var ordem = [];
        for (var c1 = 0; c1 < NC; c1++) { ordem = ordem.concat(porTipo[c1]); }
        if (agrupar) {
            ordem.sort(function (a, b) { return fonte.n[b] - fonte.n[a]; });
        }
        ctx.lineWidth = 1;
        ctx.strokeStyle = "rgba(255,255,255,0.9)";

        if (nVis <= 6000) {
            for (var o = 0; o < ordem.length; o++) {
                var q = ordem[o], cfgq = D.cats[fonte.cat[q]];
                ctx.beginPath();
                tracar(ctx, cfgq.forma, vx[q], vy[q], vr[q]);
                ctx.globalAlpha = 0.8; ctx.fillStyle = cfgq.cor; ctx.fill();
                ctx.globalAlpha = 0.9; ctx.stroke();
                hx.push(vx[q]); hy.push(vy[q]); hr.push(vr[q]); hk.push(q);
            }
        } else {
            // Acima de 20 mil itens na tela os formatos têm poucos pixels e
            // não dá para distingui-los; quadradinhos coloridos são bem mais
            // rápidos de desenhar.
            var simples = nVis > 20000;
            for (var c = 0; c < NC; c++) {
                var lista = porTipo[c];
                if (lista.length === 0) { continue; }
                ctx.globalAlpha = 0.8;
                ctx.fillStyle = D.cats[c].cor;
                if (!simples) { ctx.beginPath(); }
                for (var o2 = 0; o2 < lista.length; o2++) {
                    var q2 = lista[o2];
                    if (simples) {
                        ctx.fillRect(vx[q2] - vr[q2] * 0.8, vy[q2] - vr[q2] * 0.8, vr[q2] * 1.6, vr[q2] * 1.6);
                    } else {
                        tracar(ctx, D.cats[c].forma, vx[q2], vy[q2], vr[q2]);
                    }
                    hx.push(vx[q2]); hy.push(vy[q2]); hr.push(vr[q2]); hk.push(q2);
                }
                if (!simples) {
                    ctx.fill();
                    ctx.globalAlpha = 0.9;
                    ctx.stroke();
                }
            }
        }
        ctx.globalAlpha = 1;

        // 3) números dos grupos, dos maiores para os menores, pulando os que
        //    colidiriam com um número já desenhado
        ctx.font = "bold 11px sans-serif";
        ctx.textAlign = "center";
        ctx.textBaseline = "middle";
        ctx.lineJoin = "round";
        ctx.lineWidth = 3;
        var caixas = [];
        var porTamanho = agrupar ? ordem.filter(function (q) { return fonte.n[q] > 1; }) : [];
        for (var t = 0; t < porTamanho.length && caixas.length < 1500; t++) {
            var qq = porTamanho[t];
            var txt = rotulo(fonte.n[qq]);
            var meia = ctx.measureText(txt).width / 2 + 2;
            var colide = false;
            for (var b = 0; b < caixas.length; b++) {
                var cb = caixas[b];
                if (Math.abs(vx[qq] - cb[0]) < meia + cb[2] && Math.abs(vy[qq] - cb[1]) < 11) { colide = true; break; }
            }
            if (colide) { continue; }
            caixas.push([vx[qq], vy[qq], meia]);
            ctx.strokeStyle = "rgba(0,0,0,0.75)";
            ctx.strokeText(txt, vx[qq], vy[qq] + 0.5);
            ctx.fillStyle = "#ffffff";
            ctx.fillText(txt, vx[qq], vy[qq] + 0.5);
        }
    }
    function agendar() {
        if (zoomando) { return; }
        if (!pendente) { pendente = true; requestAnimationFrame(desenhar); }
    }

    // ---------- dica ao passar o mouse ----------
    // direção automática: abre para o lado em que há espaço, sem sair do mapa
    var dica = L.tooltip({ direction: "auto", offset: [12, 0], opacity: 0.97,
                           className: "dica-sinais" });
    var itemAtual = null;
    function descricaoDe(i) {
        return D.descr[D.d[i]] + (D.ano[i] ? "<br>Implantada em " + D.ano[i] : "");
    }
    function conteudo(k) {
        var c = fonteAtual.cat[k], n = fonteAtual.n[k];
        var titulo = "<b>" + D.cats[c].nome + "</b>";
        if (fonteAtual.ids === null) { return titulo + "<br>" + descricaoDe(k); }
        var contagem = {}, ultimo = -1;
        for (var i = 0; i < N; i++) {
            if (fonteAtual.ids[i] === k) {
                contagem[D.d[i]] = (contagem[D.d[i]] || 0) + 1;
                ultimo = i;
            }
        }
        if (n === 1) { return titulo + "<br>" + descricaoDe(ultimo); }
        var pares = Object.keys(contagem).map(function (d) { return [d, contagem[d]]; });
        pares.sort(function (a, b) { return b[1] - a[1]; });
        var linhas = pares.slice(0, 6).map(function (p) {
            return D.descr[p[0]] + " <b>×" + p[1] + "</b>";
        });
        var extra = pares.length > 6 ? "<br>…e mais " + (pares.length - 6) + " descrições" : "";
        return titulo + " — <b>" + n.toLocaleString("pt-BR") + " sinais</b><br>" + linhas.join("<br>") + extra;
    }
    function fecharDica() {
        itemAtual = null;
        mapa.closeTooltip(dica);
        mapa.getContainer().style.cursor = "";
    }
    mapa.on("mousemove", function (e) {
        var p = e.containerPoint, achado = -1;
        for (var j = hx.length - 1; j >= 0; j--) {
            var dx = hx[j] - p.x, dy = hy[j] - p.y, lim = hr[j] + 2;
            if (dx * dx + dy * dy <= lim * lim) { achado = j; break; }
        }
        if (achado === -1) {
            if (itemAtual !== null) { fecharDica(); }
            return;
        }
        var chave = hk[achado] + ":" + (agrupar ? 1 : 0) + ":" + Math.round(mapa.getZoom());
        if (chave !== itemAtual) {
            itemAtual = chave;
            dica.setContent(conteudo(hk[achado]));
        }
        dica.setLatLng(mapa.containerPointToLatLng(L.point(hx[achado], hy[achado])));
        mapa.openTooltip(dica);
        mapa.getContainer().style.cursor = "pointer";
    });
    mapa.on("movestart", fecharDica);

    // ---------- painel: tipos de sinalização e agrupamento ----------
    var painel = L.control({ position: "topright" });
    painel.onAdd = function () {
        var div = L.DomUtil.create("div", "painel-sinais");
        div.style.cssText = "background:rgba(255,255,255,0.96);color:#222;padding:10px 12px;" +
            "border-radius:6px;box-shadow:0 1px 5px rgba(0,0,0,0.4);font:13px/1.5 sans-serif;" +
            "max-height:" + Math.max(200, mapa.getSize().y - 40) + "px;overflow:auto;";
        var titulo = L.DomUtil.create("div", "", div);
        titulo.style.cssText = "font-weight:700;margin-bottom:4px;";
        titulo.textContent = "Tipo de sinalização";
        D.cats.forEach(function (cfg, c) {
            var linha = L.DomUtil.create("label", "", div);
            linha.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;white-space:nowrap;";
            var caixa = L.DomUtil.create("input", "", linha);
            caixa.type = "checkbox"; caixa.checked = true;
            caixa.addEventListener("change", function () { visivel[c] = caixa.checked; agendar(); });
            var amostra = L.DomUtil.create("canvas", "", linha);
            amostra.width = 20; amostra.height = 20;
            var cx = amostra.getContext("2d");
            cx.beginPath(); tracar(cx, cfg.forma, 10, 10, 7);
            cx.fillStyle = cfg.cor; cx.fill();
            cx.lineWidth = 1; cx.strokeStyle = "#888"; cx.stroke();
            var texto = L.DomUtil.create("span", "", linha);
            texto.innerHTML = cfg.nome + " <b>(" + cfg.n.toLocaleString("pt-BR") + ")</b>";
        });
        var sep = L.DomUtil.create("div", "", div);
        sep.style.cssText = "border-top:1px solid #ddd;margin:7px 0 6px;";
        var linhaG = L.DomUtil.create("label", "", div);
        linhaG.style.cssText = "display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:700;";
        var caixaG = L.DomUtil.create("input", "", linhaG);
        caixaG.type = "checkbox"; caixaG.checked = true;
        caixaG.addEventListener("change", function () { agrupar = caixaG.checked; fecharDica(); agendar(); });
        var textoG = L.DomUtil.create("span", "", linhaG);
        textoG.textContent = "Agrupar sinais próximos";
        var nota = L.DomUtil.create("div", "", div);
        nota.style.cssText = "font-size:11px;color:#666;max-width:250px;margin-top:3px;line-height:1.35;";
        nota.textContent = "Sinais do mesmo tipo e próximos viram um ponto com o número de " +
            "sinais. Aproxime o zoom para separá-los.";
        L.DomEvent.disableClickPropagation(div);
        L.DomEvent.disableScrollPropagation(div);
        return div;
    };
    painel.addTo(mapa);

    // Durante a animação de zoom os pontos ficariam parados enquanto o mapa
    // de fundo se move. Então eles somem quando o zoom começa e voltam,
    // já na posição certa, quando termina.
    mapa.on("zoomstart", function () {
        zoomando = true;
        fecharDica();
        canvas.style.transition = "none";
        canvas.style.opacity = "0";
    });
    mapa.on("zoomend", function () {
        zoomando = false;
        desenhar();
        requestAnimationFrame(function () {
            canvas.style.transition = "opacity 0.18s ease-out";
            canvas.style.opacity = "1";
        });
    });
    mapa.on("move", function () { posicionar(); agendar(); });
    mapa.on("resize", agendar);
    mapa.whenReady(agendar);
    agendar();
})();
{% endmacro %}
"""


class CamadaSinalizacao(MacroElement):
    _template = Template(SCRIPT_SINALIZACAO)

    def __init__(self, dados):
        super().__init__()
        self._name = "CamadaSinalizacao"
        self.dados = json.dumps(
            dados,
            ensure_ascii=False,
            separators=(",", ":"),
        ).replace("</", "<\\/")


def pontos_em_porto_alegre(df):
    dados = df.dropna(subset=["latitude", "longitude"])
    return dados[
        dados["latitude"].between(*LIMITES_LATITUDE)
        & dados["longitude"].between(*LIMITES_LONGITUDE)
    ]


def _texto_acidente(df):
    hora = df["hora"].astype("string").str[:5].fillna("--:--")
    data = df["data"].dt.strftime("%d/%m/%Y").fillna("sem data")
    tipo = df["tipo_acid"].astype("string").fillna("Tipo não informado")
    rua = df["log1"].astype("string").fillna("Local não informado")

    return [
        (
            f"<b>{html.escape(t)}</b><br>{d} às {h}<br>{html.escape(r)}<br>"
            f"Feridos: {int(fe)} (graves: {int(fg)}) · Mortes: {int(mo)}"
        )
        for t, d, h, r, fe, fg, mo in zip(
            tipo,
            data,
            hora,
            rua,
            df["feridos"].fillna(0),
            df["feridos_gr"].fillna(0),
            df["mortes"].fillna(0),
        )
    ]


def _bolinha(cor, tamanho, borda="none", sombra="none", opacidade=1):
    return (
        f'<span style="display:inline-block; width:{tamanho}px; '
        f'height:{tamanho}px; border-radius:50%; background:{cor}; '
        f'border:{borda}; box-shadow:{sombra}; opacity:{opacidade}; '
        'vertical-align:middle;"></span>'
    )


BOLINHA_GRAVE = _bolinha(COR_GRAVE, 14, "1px solid #fff", "0 0 0 1px #888")
BOLINHA_DEMAIS = _bolinha(COR_DEMAIS, 14, "1px solid #fff", "0 0 0 1px #888")


def _legenda(graves, demais):
    def inteiro(valor):
        return f"{valor:,}".replace(",", ".")

    return f"""
    <div style="position: fixed; bottom: 28px; left: 12px; z-index: 9999;
                background: rgba(255,255,255,0.95); color: #222;
                padding: 10px 14px; border-radius: 6px; font-size: 13px;
                box-shadow: 0 1px 5px rgba(0,0,0,0.4); line-height: 1.5;">
      <div style="font-weight: 700; margin-bottom: 6px;">Tipo de acidente</div>
      <div style="margin-bottom: 4px;">{BOLINHA_GRAVE}
          <b style="color:{COR_GRAVE};">Vermelho</b> — grave
          <b>({inteiro(graves)})</b></div>
      <div style="font-size: 11px; color:#666; margin: 0 0 6px 22px;">
          com feridos graves ou mortes</div>
      <div>{BOLINHA_DEMAIS}
          <b style="color:{COR_DEMAIS};">Azul</b> — demais acidentes
          <b>({inteiro(demais)})</b></div>
    </div>
    """


def _base_mapa():
    mapa = folium.Map(
        location=CENTRO_MAPA,
        zoom_start=ZOOM_MAPA,
        tiles=None,
        prefer_canvas=True,
    )
    folium.TileLayer("OpenStreetMap", control=False).add_to(mapa)
    # Fundo em tons de cinza: as cores dos pontos se destacam melhor.
    mapa.get_root().header.add_child(folium.Element(
        "<style>.leaflet-tile-pane {"
        "filter: grayscale(1) brightness(1.08) contrast(0.85);}"
        ".leaflet-control-layers {font-size: 13px;}"
        ".dica-sinais {white-space: normal; width: max-content; max-width: 320px;"
        "box-shadow: 0 1px 6px rgba(0,0,0,0.45);}</style>"
    ))
    return mapa


def mapa_pontos(df):
    mapa = _base_mapa()

    pontos = pontos_em_porto_alegre(df)
    graves = pontos[pontos["acidente_grave"]]
    demais = pontos[~pontos["acidente_grave"]]

    CamadaPontos(
        demais[["latitude", "longitude"]].round(5).values.tolist(),
        {
            "radius": 2,
            "stroke": False,
            "fillColor": COR_DEMAIS,
            "fillOpacity": 0.4,
        },
        name=f"{BOLINHA_DEMAIS} Demais acidentes",
        raio_min=1.3,
        raio_max=4,
    ).add_to(mapa)

    textos = _texto_acidente(graves)
    CamadaPontos(
        [
            [lat, lon, texto]
            for (lat, lon), texto in zip(
                graves[["latitude", "longitude"]].round(5).values.tolist(),
                textos,
            )
        ],
        {
            "radius": 3,
            "color": "#ffffff",
            "weight": 0.6,
            "fillColor": COR_GRAVE,
            "fillOpacity": 0.85,
        },
        name=f"{BOLINHA_GRAVE} Acidentes graves",
        raio_min=2.2,
        raio_max=8,
    ).add_to(mapa)

    folium.LayerControl(collapsed=False).add_to(mapa)
    mapa.get_root().html.add_child(
        folium.Element(_legenda(len(graves), len(demais)))
    )
    return mapa


def mapa_sinalizacao(sinalizacao):
    mapa = _base_mapa()

    sinais = pontos_em_porto_alegre(sinalizacao)
    contagens = sinais["categoria"].value_counts()
    ordem = list(contagens.index)
    codigos = sinais["categoria"].map({c: i for i, c in enumerate(ordem)})
    descricoes, nomes = pd.factorize(
        sinais["descricao"].astype("string").fillna("Sem descrição")
    )

    dados = {
        "lat": sinais["latitude"].round(5).tolist(),
        "lon": sinais["longitude"].round(5).tolist(),
        "cat": codigos.astype(int).tolist(),
        "d": descricoes.tolist(),
        "ano": sinais["implantacao"].dt.year.fillna(0).astype(int).tolist(),
        "cats": [
            {
                "nome": html.escape(c),
                "cor": ESTILO_SINALIZACAO.get(c, ("#999999", "circulo"))[0],
                "forma": ESTILO_SINALIZACAO.get(c, ("#999999", "circulo"))[1],
                "n": int(contagens[c]),
            }
            for c in ordem
        ],
        "descr": [html.escape(str(n)) for n in nomes],
    }

    CamadaSinalizacao(dados).add_to(mapa)
    return mapa


def mapa_calor(df):
    mapa = folium.Map(
        location=CENTRO_MAPA,
        zoom_start=ZOOM_MAPA,
        tiles="OpenStreetMap",
    )

    pontos = pontos_em_porto_alegre(df)
    if not pontos.empty:
        HeatMap(
            pontos[["latitude", "longitude"]].values.tolist(),
            radius=12,
            blur=18,
            min_opacity=0.4,
        ).add_to(mapa)

    return mapa
