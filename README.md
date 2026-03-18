# 馃殌 寮€鍙戣€呭簲鐢ㄥ叆椹绘寚鍗?(autoins.sh)

娆㈣繋涓?`autoins.sh` 璐＄尞搴旂敤锛侀€氳繃鍦?`apps/` 鐩綍涓嬪垱寤?`.conf` 閰嶇疆鏂囦欢锛屾偍鐨勫簲鐢ㄥ皢鑷姩闆嗘垚鍒拌剼鏈殑搴旂敤甯傚満涓€?
---

## 1. 蹇€熷紑濮?鍦?`apps/` 鐩綍涓嬪垱寤轰竴涓互搴旂敤鍚嶅懡鍚嶇殑閰嶇疆鏂囦欢锛屼緥濡傦細`myapp.conf`銆?
## 2. 閰嶇疆鏂囦欢妯℃澘
姣忎釜閰嶇疆鏂囦欢搴斾弗鏍奸伒寰互涓嬬粨鏋勶紝纭繚鍙橀噺鍜屽嚱鏁板懡鍚嶈鑼冿細

```bash
# --- 鍩虹淇℃伅 / Basic Information ---
local app_id="My File Name" # 鍜屾枃浠跺悕涓€鑷达紝鐢ㄤ簬瀹夎鐘舵€佹娴?/ Same as the filename, used for installation status detection.
local app_name="My App Name" # 搴旂敤鏄剧ず鍚嶇О
local app_text="A brief description" # 涓€鍙ヨ瘽绠€浠嬶紝璇存槑搴旂敤鐢ㄩ€?local app_url="https://github.com/..." # 瀹樼綉閾炬帴 / Official URL
local docker_name="myapp_container" # 瀹瑰櫒鍚姩鍚庣殑鍚嶇О / Container Name
local docker_port="8080" # 榛樿璁块棶绔彛 / Default Port
local app_size="1" # 鍗犵敤绌洪棿澶у皬(GB) / Size in GB required (1-10)

# --- 鏍稿績閫昏緫 / Core Logic ---
docker_app_install() {
    # 蹇呴』鍦?/home/docker/ 涓嬪垱寤哄簲鐢ㄧ洰褰?/ Directory creation (Mandatory)
    mkdir -p /home/docker/myapp && cd /home/docker/myapp
    # 涓嬭浇骞堕厤缃?compose 鏂囦欢 / Download compose file
    # 鍔″繀浣跨敤 gh_proxy 鍙橀噺 / Use gh_proxy for China access
    curl -L -o docker-compose.yml "${gh_proxy}https://raw.githubusercontent.com/..."
    # 绔彛澶勭悊锛堜娇鐢ㄥ彉閲忎互渚跨敤鎴疯嚜瀹氫箟锛? Port configuration (Customizable)
    sed -i "s/8080:8080/${docker_port}:8080/g" docker-compose.yml
    # 鍚姩瀹瑰櫒 / Start container
    docker compose up -d
    echo "瀹夎瀹屾垚 / Install Complete"

    # 鏄剧ず璁块棶鍦板潃鐨勫嚱鏁颁繚鐣欏嵆鍙?/ Show the function that is reserved
    check_docker_app_ip
}

docker_app_update() {
    cd /home/docker/myapp
    docker compose pull
    docker compose up -d
    echo "鏇存柊瀹屾垚 / Update Complete"
}

docker_app_uninstall() {
    cd /home/docker/myapp
    # 鍋滄骞跺垹闄ら暅鍍?/ Stop and remove images
    docker compose down --rmi all
    # 褰诲簳鐗╃悊鍒犻櫎鐩綍 / Clean up directory
    rm -rf /home/docker/myapp
    echo "鍗歌浇瀹屾垚 / Uninstall Complete"
}

# --- 娉ㄥ唽 (蹇呴』鍖呭惈) / Registration (Mandatory) ---
docker_app_plus



```

## 3. 寮哄埗瑙勮寖涓庡師鍒?
### 馃搧 鐩綍璺緞瑙勮寖
> **鏍稿績鍘熷垯锛氭暟鎹笉鍏ョ郴缁熺洏锛岀粺涓€褰掓。銆?*

* **銆愬繀椤汇€?*锛氭墍鏈夋寔涔呭寲鏁版嵁锛圴olume/Bind Mount锛夊繀椤诲瓨鍌ㄥ湪 `/home/docker/[搴旂敤鍚峕` 鐩綍涓嬨€?* **銆愮姝€?*锛氫弗绂佸皢鏁版嵁瀛樻斁鍦?`/root`銆乣/etc`銆乣/var/lib` 鎴栧叾浠栭潪鎸囧畾鏍圭洰褰曘€?* **銆愮悊鐢便€?*锛氱粺涓€璺緞鏂逛究鐢ㄦ埛杩涜涓€閿浠姐€佹暣鏈鸿縼绉讳互鍙婃潈闄愮殑缁熶竴绠＄悊銆?
### 馃攧 瀹瑰櫒鐢熷懡鍛ㄦ湡
* **寮€鏈鸿嚜鍚?*锛氱敓鎴愮殑 `docker-compose.yml` 涓繀椤诲寘鍚?`restart: always` 鎴?`restart: unless-stopped`銆?* **骞插噣鍗歌浇**锛歚docker_app_uninstall` 鍑芥暟蹇呴』鎵ц闂幆鎿嶄綔锛屽寘鍚細
    * 鍋滄骞跺垹闄ゅ鍣?(`docker compose down`)
    * 鍒犻櫎瀵瑰簲鐨勯暅鍍?(`--rmi all`)
    * **褰诲簳鐗╃悊鍒犻櫎** `/home/docker/[搴旂敤鍚峕` 鐩綍銆?
### 馃啍 鍙橀噺涓庤娉曡鏄?* **App ID**锛氬綋鍓嶇増鏈凡寮卞寲 ID 姒傚康锛屾偍鍙互鐪佺暐鎴栧～鍏ヤ换鎰忔暟鍊硷紝绯荤粺鐩墠涓昏浠?`.conf` 鏂囦欢鍚嶄綔涓哄敮涓€璇嗗埆渚濇嵁銆?* **Local 鍏抽敭瀛?*锛氱敱浜庨厤缃枃浠舵槸鍦ㄥ嚱鏁板唴閮ㄨ `source` 鍔犺浇鐨勶紝璇峰姟蹇呬繚鐣?`local` 澹版槑锛岃繖鑳芥湁鏁堥槻姝㈠彉閲忔薄鏌撹剼鏈殑鍏ㄥ眬鐜銆?
### 馃寪 缃戠粶浼樺寲
* **闀滃儚鍔犻€?*锛氫笅杞?GitHub 璧勬簮锛堝 `.yml` 鎴?`鑴氭湰`锛夋椂锛岃鍔″繀鍦?URL 鍓嶅姞涓?`${gh_proxy}` 鍙橀噺锛屼互纭繚鍥藉唴鏈嶅姟鍣ㄧ殑璁块棶鎴愬姛鐜囥€?

---


## 4. 蹇嵎鍚姩涓庤皟鐢?
涓€鏃︽偍鐨?`.conf` 鏂囦欢琚悎鍏ヤ粨搴擄紝璇ュ簲鐢ㄥ皢鑷姩杩涘叆 **鈥滅涓夋柟搴旂敤鍏ラ┗鈥?* 妯″潡銆傛澶栵紝寮€鍙戣€呭彲浠ュ悜鐢ㄦ埛鎻愪緵涓撳睘鐨勬瀬绠€瀹夎鎸囦护锛?
#### 馃殌 蹇嵎瀹夎鎸囦护妯℃澘锛?```bash
bash <(curl -sL autoins.sh) app [鏂囦欢鍚峕
```
绀轰緥锛氬鏋滄偍鐨勯厤缃枃浠跺悕涓?myapp.conf锛屽垯璋冪敤鎸囦护涓猴細 bash <(curl -sL autoins.sh) app myapp


---


## 5. 鍏ラ┗娴佺▼

1.  **鏈湴鑷祴**锛氬湪鑷繁鐨?VPS 涓婂畬鏁磋繍琛屽畨瑁呫€佹洿鏂般€佸嵏杞芥祦绋嬶紝纭繚鏃犳姤閿欍€?2.  **璺緞瀹¤**锛氭鏌?`/home/docker/` 鐩綍涓嬫槸鍚︽纭敓鎴愪簡搴旂敤鏂囦欢澶癸紝涓旀病鏈夋枃浠垛€滄孩鍑衡€濆埌鍏朵粬鍦版柟銆?3.  **鎻愪氦鐢宠**锛氬皢鎮ㄧ殑 `[搴旂敤鍚峕.conf` 鏂囦欢閫氳繃 **Pull Request** 鎻愪氦鑷虫湰浠撳簱鐨?`sh/apps/` 鐩綍銆?4.  **瀹℃牳鍙戝竷**锛氱淮鎶よ€呭鏍搁€昏緫瀹夊叏鍚庯紝鎮ㄧ殑搴旂敤灏嗘寮忎笂绾?`autoins.sh` 鑿滃崟銆?
