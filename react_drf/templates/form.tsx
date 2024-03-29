interface {{ name }}Props {
    handleSubmit: (recipe: any) => void;
}

export abstract class {{ name }} extends React.Component<{{ name }}Props, any> {
    optional_fields = [
        {% for field in optional_fields %}
        '{{ field }}',
        {% endfor %}
    ];

    state = {
        {% for field in fields %}
        {{ field.name }}: null as {{ field.type }},
        {% endfor %}
    };

    get fields() {
        const fields = {
            {% for field in fields %}
            {{ field.name }}: <input onChange={this.handleChange} type="text" name="{{ field.name }}" value={this.state.{{ field.name }}}></input>,
            {% endfor %}
        };
        return fields;
    }

    handleSubmit = (event: any) => {
        const purgedOfOptionalFields = _.reduce(this.state as any, (result: any, value: any, key: any) => {
            if (_.includes(this.optional_fields, key) && !value) {
                return result;
            }
            else {
                result[key] = value;
                return result;
            }
        }, {});

        event.preventDefault();
        this.props.handleSubmit(purgedOfOptionalFields);
    };

    handleChange = (event: any) => {
        this.setState({
            [event.target.name]: event.target.value,
        });
    };

    abstract render(): JSX.Element;
};
