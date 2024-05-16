from matplotlib import font_manager
import io
import re
from collections import defaultdict
import warnings
warnings.filterwarnings("ignore")
import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont

font_path = "C:\\Users\\dell\\Downloads\\微软雅黑.ttf"
font_name = "Microsoft YaHei"

def parse_log(lines):
    language = 'en'
    # Define the pattern for the combat lines
    combat_pattern = re.compile(
        r'\[([\d\.\s:]+)\]\s+\(combat\)\s+(\d+)\s+(from|to)\s+(.+?)\s+-\s+(.+?)\s+-\s+(.+)')
    repair_pattern = re.compile(
        r'\[([\d\.\s:]+)\]\s+\(combat\)\s+(\d+)\s+(remote armor repaired|remote shield boosted)\s+(to|by)\s+(.+?)\s+-\s+(.+)')
    # [ 2024.05.13 03:53:04 ] (combat) Your group of 250mm Railgun II misses Funny RUA completely - 250mm Railgun II
    you_miss_pattern = re.compile(
        r'\[([\d\.\s:]+)\] \(combat\) Your group of (.+?) misses (.+?) completely - \2')
    miss_you_pattern = re.compile(
        r'\[([\d\.\s:]+)\] \(combat\) (.+?) misses you completely - (.+)')
    # [ 2024.05.15 22:54:46 ] (combat) Warp disruption attempt from  Claw │  [NERV] to you!
    point_pattern = re.compile(
        r'\[([\d\.\s:]+)\] \(combat\) Warp (disruption|scramble) attempt from (.+?) to (.+)')

    listener_name = ''
    if '游戏记录' in lines[1]:
        combat_pattern = re.compile(
            r'\[([\d\.\s:]+)\]\s+\(combat\)\s+(\d+)\s+(来自|对)\s+(.+?)\s+-\s+(.+?)\s+-\s+(.+)')
        repair_pattern = re.compile(
            r'\[([\d\.\s:]+)\]\s+\(combat\)\s+(\d+)\s*(远程装甲维修量|远程护盾回充增量)\s*(至|由)\s*(.+?)\s+-\s+(.+)')
        # 你的一组250mm Railgun II*完全没有打中DarKdeZ Ever - 250mm Railgun II*
        you_miss_pattern = re.compile(
            r'\[([\d\.\s:]+)\] \(combat\) 你的一组(.+?)\*完全没有打中(.+?) - \2')
        miss_you_pattern = re.compile(
            r'\[([\d\.\s:]+)\] \(combat\) (.+?)完全没有打中你 - (.+)')
        point_pattern = re.compile(
            r'\[([\d\.\s:]+)\] \(combat\) (.+?)\s*试图跃迁(扰频|扰断)\s(.+)')

        # Extract the name of the listener from the second line of the file
        listener_name = re.search(r'收听者: (.+)', lines[2]).group(1)
        print(f"战犯: {listener_name}")
        language = 'zh'
    else:
        # Extract the name of the listener from the second line of the file
        listener_name = re.search(r'Listener: (.+)', lines[2]).group(1)
        print(f"Zhanfan: {listener_name}")

    results = []

    # for line in lines:
    for i in range(len(lines)-1):
        line = lines[i]
        while i < len(lines)-1 and not lines[i+1].startswith('[ '):
            line = line.strip() + lines[i+1]
            i += 1
        if "197-variant" in line:
            continue
        # Remove HTML tags
        clean_line = re.sub('<[^<]+?>', '', line.strip())
        # print(clean_line)
        # Match the cleaned line against the combat pattern
        match_damage = combat_pattern.match(clean_line)
        # print(match)
        if match_damage:
            # print(clean_line)
            time_stamp = match_damage.group(1)
            dmg_number = match_damage.group(2)
            direction = match_damage.group(3)
            game_id = match_damage.group(4).strip()
            weapon = match_damage.group(5).strip()
            hit_efficiency = match_damage.group(6).strip()
            damage = {
                "type": "damage",
                "time": time_stamp,
                "damage_number": int(dmg_number),
                "direction": direction,
                "game_id": game_id,
                "weapon": weapon,
                "hit_efficiency": hit_efficiency
            }
            results.append(damage)
            # print(damage)
            continue
        # Match the cleaned line against the repair pattern
        match_repair = repair_pattern.match(clean_line)
        # print(match)
        if match_repair:
            # print(clean_line)
            time_stamp = match_repair.group(1)
            rep_number = match_repair.group(2)
            rep_type = match_repair.group(3)
            direction = match_repair.group(4)
            game_id = match_repair.group(5).strip()
            module = match_repair.group(6).strip()
            rep = {
                "type": "repair",
                "time": time_stamp,
                "rep_number": int(rep_number),
                "rep_type": rep_type,
                "direction": direction,
                "game_id": game_id,
                "module": module
            }
            results.append(rep)
            # print(rep)
            continue
        # Match the cleaned line against the you miss pattern
        match_you_miss = you_miss_pattern.match(clean_line)
        if match_you_miss:
            time_stamp = match_you_miss.group(1)
            weapon_type = match_you_miss.group(2)
            game_id = match_you_miss.group(3)
            damage = {
                "type": "damage",
                "time": time_stamp,
                "damage_number": 0,
                "direction": "to",
                "game_id": game_id,
                "weapon": weapon_type,
                "hit_efficiency": "Misses"
            }
            results.append(damage)
            # print(damage)
            continue
        # Match the cleaned line against the miss you pattern
        match_miss_you = miss_you_pattern.match(clean_line)
        if match_miss_you:
            time_stamp = match_miss_you.group(1)
            game_id = match_miss_you.group(2)
            weapon_type = match_miss_you.group(3)
            damage = {
                "type": "damage",
                "time": time_stamp,
                "damage_number": 0,
                "direction": "from",
                "game_id": game_id,
                "weapon": weapon_type,
                "hit_efficiency": "Misses"
            }
            results.append(damage)
            # print(damage)
            continue
        # results.append({"line": clean_line})
        match_point = point_pattern.match(clean_line)
        if match_point:
            # print(match_point)
            time_stamp = match_point.group(1)
            point_type = match_point.group(2)
            point_from = match_point.group(3)
            point_to = match_point.group(4)
            if language == 'zh':
                time_stamp = match_point.group(1)
                point_type = match_point.group(3)
                point_from = match_point.group(2)
                point_to = match_point.group(4)
                
            if point_to.endswith('!') or point_to.endswith('！'):
                point_to = point_to[:-1]
            point = {
                "type": "point",
                "time": time_stamp,
                "point_type": point_type,
                "point_from": point_from,
                "point_to": point_to,
            }
            if point_from == 'you' or point_to == 'you' or \
                point_from == '你' or point_to == '你':
                results.append(point)
            # print(point)
    return results, language, listener_name

def statistics(damages, language, name):
 # Initialize data structures
    weapon_stats = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    rep_stats = defaultdict(lambda: defaultdict(int))
    damage_stats = defaultdict(int)
    points = []
    if language == 'en':
        dmg_to = 'to'
        dmg_from = 'from'
        rep_to = 'to'
        rep_by = 'by'
    elif language == 'zh':
        dmg_to = '对'
        dmg_from = '来自'
        rep_to = '至'
        rep_by = '由'
    else:
        return "Unknown language"
    # Filter and aggregate data
    for damage in damages:
        if damage['type'] == 'damage' and damage['direction'] == dmg_to:
            weapon_stats['to'][damage['weapon']]['total_damages'].append(
                damage['damage_number'])
            weapon_stats['to'][damage['weapon']]['hit_efficiencies'].append(
                damage['hit_efficiency'])
            damage_stats[damage['game_id']] += damage['damage_number']
        if damage['type'] == 'damage' and damage['direction'] == dmg_from:
            weapon_stats['from'][damage['weapon']]['total_damages'].append(
                damage['damage_number'])
            weapon_stats['from'][damage['weapon']]['hit_efficiencies'].append(
                damage['hit_efficiency'])
        if damage['type'] == 'repair' and damage['direction'] == rep_to:
            rep_stats['to'][damage['game_id']] += damage['rep_number']
        if damage['type'] == 'repair' and damage['direction'] == rep_by:
            rep_stats['by'][damage['game_id']] += damage['rep_number']
        if damage['type'] == 'point':
            points.append(damage)
            # print(damage)
    # Prepare output dictionary

    damage_detail = []
    for game_id, damage in damage_stats.items():
        damage_detail.append((game_id, damage))
    damage_detail = sorted(damage_detail, key=lambda item: item[1], reverse=True)

    damage_done = []
    for weapon, stats in weapon_stats['to'].items():
        total_damages = sum(stats['total_damages'])
        efficiency_count = {}
        for efficiency in stats['hit_efficiencies']:
            if efficiency in efficiency_count:
                efficiency_count[efficiency] += 1
            else:
                efficiency_count[efficiency] = 1

        # Calculate percentages
        total_efficiency_occurrences = sum(efficiency_count.values())
        efficiency_percentages = {eff: (
            count / total_efficiency_occurrences * 100) for eff, count in efficiency_count.items()}
        damage_done.append((weapon, total_damages, efficiency_percentages))
    damage_done = sorted(damage_done, key=lambda item: item[1], reverse=True)
        
    damage_receive = []
    for weapon, stats in weapon_stats['from'].items():
        total_damages = sum(stats['total_damages'])
        efficiency_count = {}
        for efficiency in stats['hit_efficiencies']:
            if efficiency in efficiency_count:
                efficiency_count[efficiency] += 1
            else:
                efficiency_count[efficiency] = 1

        # Calculate percentages
        total_efficiency_occurrences = sum(efficiency_count.values())
        efficiency_percentages = {eff: (
            count / total_efficiency_occurrences * 100) for eff, count in efficiency_count.items()}
        damage_receive.append((weapon, total_damages, efficiency_percentages))
    damage_receive = sorted(damage_receive, key=lambda item: item[1], reverse=True)

    rep_done = []
    for man, amount in rep_stats['to'].items():
        rep_done.append((man, amount))
    rep_done = sorted(rep_done, key=lambda item: item[1], reverse=True)
    rep_receive = []
    for man, amount in rep_stats['by'].items():
        rep_receive.append((man, amount))
    rep_receive = sorted(rep_receive, key=lambda item: item[1], reverse=True)

    output = {
        'name': name,
        'damage_detail': damage_detail,
        'damage_done': damage_done,
        'damage_receive': damage_receive,
        'rep_done': rep_done,
        'rep_receive': rep_receive,
        'points': points

    }
    return output


def draw_plots_from_stats(stats, language):
    total_damage = 0
    total_rep = 0
    total_damage_rec = 0
    for rep in stats['rep_done']:
        total_rep += rep[1]
    for rec in stats['damage_receive']:
        total_damage_rec += rec[1]
    for damage in stats['damage_done']:
        total_damage += damage[1]
    # print(total_rep)
    # draw rep receive and damage receive chart
    rep_dmg_receive_img = None
    if stats['rep_receive'] or stats['damage_receive']: 
        rep_dmg_receive_img = rep_dmg_receive_plot(stats['rep_receive'], [(item[0], item[1])
                        for item in stats['damage_receive']], language)
        # rep_dmg_receive_img.show()
    points_img = points_plot(stats['points'], language)
    # points_img.show()
    rep_done_img = None
    damge_done_img = None
    damage_detail_img = None
    # output_img = None
    # print(stats['name'])
    overall_img = overall_img_draw((1000, 200), f'Name: {stats["name"]}')
    # overall_img.show()
    if total_rep > 2000:
        rep_done_img = rep_done_plot(stats['rep_done'], language)
        # rep_done_img.show()
        text = f'Name: {stats["name"]}\n\n Total Repair Amount:  {total_rep:,}\n\nTotal Damage Receive: {total_damage_rec:,}'
        overall_img = overall_img_draw(rep_done_img.size, text)
        # overall_img.show()
        # output_img = assembly_img(
        #     [overall_img, rep_done_img, rep_dmg_receive_img, points_img])

    else:
        # overall_img = None
        if stats['damage_done']:
            damge_done_img = damage_done_plot(stats['damage_done'], language)
            # damge_done_img.show()
            main_name, main_dmg, main_eff = stats['damage_done'][0]
            main_accr = main_eff.get('Hits', 0)+main_eff.get('Penetrates', 0) + \
            main_eff.get('Smashes', 0)+main_eff.get('Wrecks', 0) + \
            main_eff.get('命中', 0)+main_eff.get('穿透', 0) + \
            main_eff.get('强力一击', 0)+main_eff.get('致命一击', 0)
            text = f'Name: {stats["name"]}\n\n  Total Damage Done:  {total_damage:,}\n\n{main_name}: {main_accr:.1f}% Hit\n\nTotal Damage Receive: {total_damage_rec:,}'
            overall_img = overall_img_draw(damge_done_img.size, text)
        if stats['damage_detail']: 
            damage_detail_img = damage_detail_table(stats['damage_detail'], language)
            # damage_detail_img.show()
        # overall_img.show()
        # output_img = assembly_img(
        #     [overall_img, damge_done_img, rep_dmg_receive_img, damage_detail_img, points_img])
    # print(points_img.size)
    output_img = assembly_img(
        [overall_img, rep_done_img, damge_done_img, rep_dmg_receive_img, damage_detail_img, points_img])

    # output_img.save('zhanfan.png')
    return output_img
    
def rep_dmg_receive_plot(list1, list2=[], language = 'en'):
    # print(list1)
    # print(list2)
    names1 = [item[0][:30] for item in list1]
    values1 = [item[1] for item in list1]

    # Names and values for the second list
    names2 = [item[0][:30] for item in list2]
    values2 = [item[1] for item in list2]

    # Combine names from both lists maintaining the original order
    all_names = names1 + names2[:5]

    # Prepare data for plotting
    data1 = values1 + [0 for item in values2[:5]]
    data2 = [0 for item in values1] + values2[:5]
    #print(all_names)
    #print(data1)
    #print(data2)
    # X locations for the groups
    x = range(len(all_names))
    width = 0.35  # width of the bars

    fig, ax = plt.subplots(figsize=(10,5))
    rects1 = ax.bar(x, data1, width, label='Rep received', color='blue')
    rects2 = ax.bar(x, data2, width, bottom=data1,
                    label='DMG received', color='red')

    # Add some text for labels, title, and custom x-axis tick labels, etc.
    ax.set_xlabel('Source')
    ax.set_ylabel('Amount')
    ax.set_title('Rep and Damage Received by Sources')
    ax.set_xticks(x)
    ax.set_xticklabels(all_names, rotation= -10, ha='center', fontsize=10)
    ax.legend()

    # Function to attach a text label above each bar, showing its height
    def autolabel(rects, data):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect, value in zip(rects, data):
            height = rect.get_height()
            if value:  # Only label bars with non-zero height
                ax.annotate('{}'.format(value),
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom')

    autolabel(rects1, data1)
    autolabel(rects2, data2)
    plt.tight_layout()
    return plot2image(fig, plt, language)

def rep_done_plot(list1, language='en'):
    # print(list1)
    names1 = [item[0][:30] for item in list1]
    values1 = [item[1] for item in list1]

    # X locations for the groups
    x = range(len(names1))
    width = 0.35  # width of the bars

    fig, ax = plt.subplots(figsize=(10, 5))
    rects1 = ax.bar(x, values1, width, label='Rep applied', color='blue')

    # Add some text for labels, title, and custom x-axis tick labels, etc.
    ax.set_xlabel('Target')
    ax.set_ylabel('Amount')
    ax.set_title('Rep Applied to Allies')
    ax.set_xticks(x)
    ax.set_xticklabels(names1, rotation=-10, ha='center', fontsize=10)
    ax.legend()

    # Function to attach a text label above each bar, showing its height
    def autolabel(rects, data):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect, value in zip(rects, data):
            height = rect.get_height()
            if value:  # Only label bars with non-zero height
                ax.annotate('{}'.format(value),
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom')

    autolabel(rects1, values1)
    plt.tight_layout()
    return plot2image(fig, plt, language)

def damage_done_plot(list1, language='en'):
    # print(language)
    weapon, damage, efficiency = list1[0]
    names1 = ['Misses', 'Grazes', 'Glances Off', 'Hits', 'Penetrates', 'Smashes', 'Wrecks']
    if language == 'zh':
        names1 = ['Misses', '轻轻擦过', '擦过',
                  '命中', '穿透', '强力一击', '致命一击']
    values1 = [efficiency.get(name, 0) for name in names1]
    names1[0] = 'Miss'

    # X locations for the groups
    x = range(len(names1))
    width = 0.35  # width of the bars

    fig, ax = plt.subplots(figsize=(10, 5))
    rects1 = ax.bar(x, values1, width, label='', color='red')

    # Add some text for labels, title, and custom x-axis tick labels, etc.
    ax.set_xlabel('')
    ax.set_ylabel('Percentage')
    ax.set_title('Main Weapon Damage Application Count')
    ax.set_xticks(x)
    ax.set_xticklabels(names1, rotation=-10, ha='center', fontsize=10)
    # count weapons usage %
    total_damage = 0
    for weapon, damage, efficiency in list1:
        total_damage += damage
    text = ''
    for weapon, damage, efficiency in list1:
        text += f'{weapon}: {(damage/total_damage*100):.1f}%\n'
    ax.legend((text.strip(),), loc = 'upper right')

    # Function to attach a text label above each bar, showing its height
    def autolabel(rects, data):
        """Attach a text label above each bar in *rects*, displaying its height."""
        for rect, value in zip(rects, data):
            height = rect.get_height()
            if value:  # Only label bars with non-zero height
                ax.annotate(f'{value:.1f}',
                            xy=(rect.get_x() + rect.get_width() / 2, height),
                            xytext=(0, 3),  # 3 points vertical offset
                            textcoords="offset points",
                            ha='center', va='bottom')

    autolabel(rects1, values1)
    plt.tight_layout()
    return plot2image(fig, plt, language)


def points_plot(raw_data, language):
    data = [(f"[ {line['time']} ]", line['point_type'], line['point_from'][:30], line['point_to'][:30]) for line in raw_data]
    if not data:
        return None
    # Create a new figure and axis (but don't display the axis)
    # print(len(data))
    fig, ax = plt.subplots(figsize=(10, 2 + max(2, 0.2 * len(data))))
    # ax.axis('tight')
    ax.axis('off')
    ax.set_title('Tackle Applied and Received')

    # plt.subplots_adjust(top=2.01)
    # Column headers
    column_labels = ['Time', 'Type', 'From', 'To']
    column_widths = [0.3, 0.1, 0.3, 0.3]
    # Create the table
    table = ax.table(cellText=data, colLabels=column_labels,
                     colWidths=column_widths,rowLoc='center', colLoc='center', loc='center')

    # Optionally, you can adjust the table properties or scale it
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for key, cell in table.get_celld().items():
        if key[1] :  # Column 1 (second column, since index starts at 0)
            # Horizontally align text at cente
            cell.set_text_props(ha='center')
    fig.tight_layout()

    # plt.show()
    return plot2image(fig, plt, language)

def damage_detail_table(data, language):
    data = [(item[0], f'{item[1]:,}') for item in data]
    # Create a new figure and axis (but don't display the axis)
    fig, ax = plt.subplots(figsize=(10, 2 + max(2, 0.2 * len(data))))
    # ax.axis('tight')
    ax.axis('off')
    ax.set_title('Damage Applied')

    # Column headers
    column_labels = ['Target', 'Damage']
    column_widths = [0.7, 0.3]
    # Create the table
    table = ax.table(cellText=data, colLabels=column_labels,
                     colWidths=column_widths, rowLoc='center', colLoc='center', loc='center')

    # Optionally, you can adjust the table properties or scale it
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    for key, cell in table.get_celld().items():
        if key[1] == 1:  # Column 1 (second column, since index starts at 0)
            # Horizontally align text at cente
            cell.set_text_props(ha='center')

    fig.tight_layout()
    
    # plt.show()
    return plot2image(fig, plt, language)


def plot2image(fig, plt, language = 'en'):
    # if language == 'zh':
    font_manager.fontManager.addfont(font_path)
    plt.rcParams['font.sans-serif'] = font_name
    # Save the plot to a BytesIO object
    img_buffer = io.BytesIO()
    plt.savefig(img_buffer, format='png')
    plt.close(fig)  # Close the plot to free up memory

    # Seek to the beginning of the stream so we can read its content
    img_buffer.seek(0)

    # Load this image into a PIL Image object (optional, for demonstration)
    image = Image.open(img_buffer)

    # Return the PIL Image object (or the BytesIO object itself if you prefer)
    return image

def overall_img_draw(size, text):
    width, height = size
    white_image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(white_image)
    font = ImageFont.truetype(font_path, 42)
    _, _, w, h = draw.textbbox((0, 0), text, font=font)
    draw.text(((width-w)/2, (height-h)/2), text, font=font, fill='black')
    return white_image

def assembly_img(images):
    images = [image for image in images if image]
    if not images:
        return None
    # Determine the maximum width and total height
    max_width = max(image.width for image in images)
    total_height = sum(image.height for image in images)

    # Create a new image with the appropriate size
    result_image = Image.new('RGB', (max_width, total_height), color=(
        255, 255, 255))  # white background

    # Paste each image into the result image
    current_y = 0  # starting y position
    for image in images:
        # Paste the current image into the result image
        result_image.paste(image, (0, current_y))
        current_y += image.height  # update the y position for the next image

    return result_image

def all_in_one(lines):
    log_results, language, name = parse_log(lines)
    output_stats = statistics(log_results, language, name)
    return draw_plots_from_stats(output_stats, language)

if __name__ == "__main__":
    # Example usage (assuming the logs are saved locally)
    file_path = 'your_log_file.txt'
    with open(file_path, 'r', encoding='utf-8') as file:
        lines = file.readlines()
        output_image = all_in_one(lines)
        output_image.save('zhanfan.png')
        output_image.show()
